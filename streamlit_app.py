import numpy as np
import pandas as pd
import streamlit as st
import json
from io import StringIO
from datetime import datetime, timedelta
import re
import csv
import zipfile
import altair as alt

"""
# Let's analyse your Tockler and Oura data!
"""

# Sidebar for accepting input parameters
with st.sidebar:
    # Load AWT data
    st.header('Upload your data')
    st.markdown('**1. Tockler/AWT data**')
    awt_uploaded_file = st.file_uploader("Upload your Tockler data here. You can export your data by going to Tockler > Search > Set a time period > Export to CSV.", type='csv', key='awt')

    # Load Oura data as ZIP
    st.markdown('**2. Oura data**')
    oura_data_zip = st.file_uploader("Upload your Oura data (ZIP file) here.", type='zip', key='oura')

    # Load Survey results data
    st.markdown('**3. Survey results**')
    survey_uploaded_file = st.file_uploader("Upload your survey results here. The CSV should contain 5 columns: Date, Productivity, Vigor, Dedication, Absorption.")

    # Load Google Maps data
    st.markdown('**4. Google Maps Timeline**')
    google_maps_uploaded_files = st.file_uploader("Upload your Google Maps Timeline data here. You can export your data by going to https://myaccount.google.com/yourdata/maps?hl=en > Download your Maps data > Check Location History (Timeline). There should be one JSON file per month.", type='json', accept_multiple_files=True)

# Function to process 'oura_daily-readiness' JSON data
def process_daily_readiness(data):
    readiness_data = []
    for entry in data["daily_readiness"]:
        contributors = entry["contributors"]
        day_data = {"day": entry["day"], "readiness_score": entry["score"], "temperature_deviation": entry.get("temperature_deviation", None)}
        day_data.update(contributors)
        readiness_data.append(day_data)
    return pd.DataFrame(readiness_data)

# Function to process 'oura_daily-sleep' JSON data
def process_daily_sleep(data):
    sleep_data = []
    for entry in data["daily_sleep"]:
        contributors = entry["contributors"]
        day_data = {"day": entry["day"], "sleep_score": entry["score"]}
        day_data.update(contributors)
        sleep_data.append(day_data)
    return pd.DataFrame(sleep_data)

# Function to process 'oura_heart-rate' JSON data (assuming this function is defined elsewhere)
def process_heart_rate(data):
    df = pd.DataFrame(data["heart_rate"])
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['day'] = df['timestamp'].dt.date  # Create 'day' column from 'timestamp'
    
    # Convert 'hrv' and 'bpm' columns to numeric, handling errors
    numeric_columns = ['hrv', 'bpm']
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Drop rows with NaN values in 'hrv' or 'bpm'
    df = df.dropna(subset=numeric_columns)
    
    return df

# Function to plot scores per day using Altair
def plot_scores(df_readiness, df_sleep):
    # Merge readiness and sleep scores on 'day' column
    df_combined = pd.merge(df_readiness, df_sleep, on='day', how='outer')
    
    # Melt dataframe to long format for Altair plotting
    df_combined_melt = pd.melt(df_combined, id_vars=['day'], value_vars=['readiness_score', 'sleep_score'], var_name='type', value_name='score')
    
    chart = alt.Chart(df_combined_melt).mark_line(point=True).encode(
        x='day:T',
        y=alt.Y('score:Q', title='Score'),
        color='type:N'
    ).properties(
        title='Readiness and Sleep Scores per Day'
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

# Function to plot average bpm and hrv scores per 5-minute interval across all days
def plot_heart_rate_average_all_days(df_heart_rate):
    # Round timestamps to nearest five minutes
    df_heart_rate['timestamp'] = df_heart_rate['timestamp'].dt.round('5min')
    
    # Extract hour and minute for grouping
    df_heart_rate['hour'] = df_heart_rate['timestamp'].dt.hour
    df_heart_rate['minute'] = df_heart_rate['timestamp'].dt.minute
    
    # Group by hour, minute and calculate mean bpm and hrv scores
    df_avg = df_heart_rate.groupby(['hour', 'minute'])[['hrv', 'bpm']].mean().reset_index()
    
    # Create a time column combining hour and minute for plotting
    df_avg['time'] = pd.to_datetime({
        'year': 2000,  # arbitrary year
        'month': 1,    # arbitrary month
        'day': 1,      # arbitrary day
        'hour': df_avg['hour'],
        'minute': df_avg['minute']
    })
    
    # Melt dataframe to long format for Altair plotting
    df_avg_melt = pd.melt(df_avg, id_vars=['time'], value_vars=['hrv', 'bpm'], var_name='measurement', value_name='value')
    
    # Explicitly convert 'measurement' to categorical data type
    df_avg_melt['measurement'] = df_avg_melt['measurement'].astype('category')
    
    # Create the scatter plot (dots)
    chart = alt.Chart(df_avg_melt).mark_line().encode(
        x=alt.X('hoursminutes(time):T', title='Time of Day'),
        y=alt.Y('value:Q', title='Score'),
        color=alt.Color('measurement:N', title='Measurement'),
        tooltip=[alt.Tooltip('time:T', title='Time', format='%H:%M'),
            alt.Tooltip('measurement'),
            alt.Tooltip('value')]
    ).properties(
        title='Average Heart Rate Data (bpm and hrv) Across All Days Per 5-Minute Interval',
        width=800
    ).interactive()
    
    st.altair_chart(chart, use_container_width=True)

# Function to convert timestamp format and adjust timezone
def format_timestamp(timestamp):
    # Regular expression to match timestamp with or without milliseconds
    match = re.match(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?Z", timestamp)
    if match:
        base_time = match.group(1)
        dt = datetime.strptime(base_time, "%Y-%m-%dT%H:%M:%S")
        dt = dt + timedelta(hours=2)  # Adjusting to UTC+2 for Netherlands
        formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
        return formatted_time
    else:
        raise ValueError(f"Invalid timestamp format: {timestamp}")


# Main section for processing AWT data
if awt_uploaded_file is not None:
    try:
        # Read the uploaded CSV file into a dataframe
        awt_stringio = StringIO(awt_uploaded_file.getvalue().decode('latin1'))
        
        # Explicitly set the delimiter as semicolon
        dataframe_awt = pd.read_csv(awt_stringio, delimiter=';')

        # Drop the 'Type' column if it exists
        if 'Type' in dataframe_awt.columns:
            dataframe_awt = dataframe_awt.drop(columns=['Type'])

        # Display the first 5 rows of the dataframe
        st.subheader("Tockler Data")
        st.write(dataframe_awt.head())

        # Remove rows where 'Begin' is empty
        dataframe_awt = dataframe_awt.dropna(subset=['Begin'])
        dataframe_awt = dataframe_awt[dataframe_awt['Begin'] != '']

        # Remove rows where 'Title' is 'NO_TITLE'
        dataframe_awt = dataframe_awt[dataframe_awt['Title'] != 'NO_TITLE']

        # Initialize lists to store merged rows
        merged_rows = []

        # Convert 'App' column to string
        dataframe_awt['App'] = dataframe_awt['App'].astype(str)

        # Convert 'Title' column to string
        dataframe_awt['Title'] = dataframe_awt['Title'].astype(str)

        # Iterate over the DataFrame to merge consecutive rows
        current_row = None
        for index, row in dataframe_awt.iterrows():
            if current_row is None:
                current_row = row
            else:
                # Check if the current row is consecutive with the previous row
                if row['Begin'] == current_row['End']:
                    # Merge titles and update End time
                    current_row['App'] += '; ' + row['App']
                    current_row['Title'] += '; ' + row['Title']
                    current_row['End'] = row['End']
                else:
                    # Append the current merged row to the list
                    merged_rows.append(current_row)
                    # Start a new merged row
                    current_row = row

        # Append the last merged row
        if current_row is not None:
            merged_rows.append(current_row)

        # Create a new DataFrame with the merged rows
        dataframe_merged_awt = pd.DataFrame(merged_rows)

        # Filter out rows with unwanted titles
        dataframe_merged_awt = dataframe_merged_awt[~dataframe_merged_awt['Title'].isin(['NO_TITLE', 'Windows Default Lock Screen'])]

        # Reset the index of the new DataFrame
        dataframe_merged_awt.reset_index(drop=True, inplace=True)

        # Define a custom function to find the most occurring title in a semicolon-separated string
        def find_most_occurring_title(merged_titles):
            titles = merged_titles.split(';')
            title_counts = pd.Series(titles).value_counts()
            most_occuring_title = title_counts.idxmax()
            return most_occuring_title

        # Apply the custom function to each row in the DataFrame and create a new column
        dataframe_merged_awt['Most_occuring_title'] = dataframe_merged_awt['Title'].apply(find_most_occurring_title)

        st.subheader("Tockler data merged to continued work slots")
        st.write(dataframe_merged_awt.head())

    except pd.errors.ParserError as e:
        st.error(f"Error parsing AWT CSV file: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

if oura_data_zip is not None:
    with zipfile.ZipFile(oura_data_zip, 'r') as zip_ref:
        file_list = zip_ref.namelist()
        
        # Initialize dataframes
        df_readiness = None
        df_sleep = None
        df_heart_rate = None

        # Process each file in the ZIP
        for file_name in file_list:
            with zip_ref.open(file_name) as file:
                file_content = file.read()
                json_data = json.loads(file_content)
                
                if file_name.startswith("oura_daily-readiness"):
                    df_readiness = process_daily_readiness(json_data)
                elif file_name.startswith("oura_daily-sleep"):
                    df_sleep = process_daily_sleep(json_data)
                elif file_name.startswith("oura_heart-rate"):
                    df_heart_rate = process_heart_rate(json_data)
        
        # Display dataframes
        if df_readiness is not None:
            st.subheader("Daily Readiness Data")
            st.dataframe(df_readiness.head())
        
        if df_sleep is not None:
            st.subheader("Daily Sleep Data")
            st.dataframe(df_sleep.head())
        
        if df_heart_rate is not None:
            st.subheader("Heart Rate Data")
            st.dataframe(df_heart_rate.head())
            plot_heart_rate_average_all_days(df_heart_rate)

        if df_sleep is not None and df_readiness is not None:
            plot_scores(df_readiness, df_sleep)

# Main section for processing AWT data
if awt_uploaded_file is not None and oura_data_zip is not None:
    # Create a new dataframe by copying the existing one
    awt_with_hrv = dataframe_merged_awt.copy()

    # Initialize new columns for HRV and BPM averages and counts
    awt_with_hrv['avg_hrv'] = None
    awt_with_hrv['avg_bpm'] = None
    awt_with_hrv['count_hrv'] = None
    awt_with_hrv['count_bpm'] = None

    # Iterate over the rows of dataframe_merged_awt
    for index, row in dataframe_merged_awt.iterrows():
        begin = row['Begin']
        end = row['End']
        
        # Filter df_heart_rate to get rows within the time period
        mask = (df_heart_rate['timestamp'] >= begin) & (df_heart_rate['timestamp'] <= end)
        filtered_heart_rate = df_heart_rate.loc[mask]
        
        if not filtered_heart_rate.empty:
            # Calculate average HRV and BPM
            avg_hrv = filtered_heart_rate['hrv'].mean()
            avg_bpm = filtered_heart_rate['bpm'].mean()
            
            # Count the number of HRV and BPM records
            count_hrv = filtered_heart_rate['hrv'].count()
            count_bpm = filtered_heart_rate['bpm'].count()
            
            # Update the new dataframe with these values
            awt_with_hrv.at[index, 'avg_hrv'] = avg_hrv
            awt_with_hrv.at[index, 'avg_bpm'] = avg_bpm
            awt_with_hrv.at[index, 'count_hrv'] = count_hrv
            awt_with_hrv.at[index, 'count_bpm'] = count_bpm

    # Fill None values with 0 before converting to integers
    awt_with_hrv['count_hrv'] = awt_with_hrv['count_hrv'].fillna(0).astype(int)
    awt_with_hrv['count_bpm'] = awt_with_hrv['count_bpm'].fillna(0).astype(int)

    # Optional: Convert avg_hrv and avg_bpm to float, if necessary
    awt_with_hrv['avg_hrv'] = awt_with_hrv['avg_hrv'].astype(float)
    awt_with_hrv['avg_bpm'] = awt_with_hrv['avg_bpm'].astype(float)

    st.subheader("Work slots with average HRV and BPM")
    st.write(awt_with_hrv)

    # Get the value counts of the 'Most_occuring_title' column
    title_counts = awt_with_hrv['Most_occuring_title'].value_counts().reset_index()

    # Rename the columns for better readability
    title_counts.columns = ['Most_occuring_title', 'count']

    # Create the new dataframe
    frequent_titles_unique = title_counts

    st.write(frequent_titles_unique)

    @st.cache_data
    def convert_df(df):
        return df.to_csv(index=False).encode('utf-8')

    csv = convert_df(frequent_titles_unique)

    st.download_button(
        "Download CSV",
        csv,
        "file.csv",
        "text/csv",
        key='download-csv'
    )

# Check if a Survey results file has been uploaded
if survey_uploaded_file is not None:
    try:
        # Read the uploaded CSV file into a dataframe
        survey_stringio = StringIO(survey_uploaded_file.getvalue().decode('utf-8'))
        dialect = csv.Sniffer().sniff(survey_stringio.read(1024))
        survey_stringio.seek(0)
        dataframe_survey = pd.read_csv(survey_stringio, delimiter=dialect.delimiter)

        # Display the first 5 rows of the dataframe
        st.subheader("Survey results data")
        st.write(dataframe_survey.head())

        # Convert survey date format to match
        dataframe_survey['Date'] = pd.to_datetime(dataframe_survey['Date'], format='%d-%m-%Y').dt.strftime('%Y-%m-%d')

    except pd.errors.ParserError as e:
        st.error(f"Error parsing Survey CSV file: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")

# Check if Google Maps files have been uploaded 
if google_maps_uploaded_files:
    place_visits = []

    # Iterate over each uploaded file
    for uploaded_file in google_maps_uploaded_files:
        # Read the JSON file
        maps_data = json.load(uploaded_file)

        # Iterate over each entry in the JSON data
        for entry in maps_data.get("timelineObjects", []):
            if "placeVisit" in entry:
                place_visit = entry["placeVisit"]
                location = place_visit.get("location", {})
                duration = place_visit.get("duration", {})

                # Extract the required information
                place_visited = location.get("address", "Unknown")
                start_visit = duration.get("startTimestamp", "Unknown")
                end_visit = duration.get("endTimestamp", "Unknown")

                # Format the timestamps
                if start_visit != "Unknown":
                    start_visit = format_timestamp(start_visit)
                if end_visit != "Unknown":
                    end_visit = format_timestamp(end_visit)

                # Append the data as a dictionary to the list
                place_visits.append({
                    "Place_visited": place_visited,
                    "Start_visit": start_visit,
                    "End_visit": end_visit
                })

    # Create a DataFrame from the list of place visits
    dataframe_locations = pd.DataFrame(place_visits, columns=["Place_visited", "Start_visit", "End_visit"])

    # Display the DataFrame in Streamlit
    st.write("Google Maps locations visited:")
    st.write(dataframe_locations)

    # Initialize a list to store the enriched rows
    enriched_rows = []

    # Iterate over the rows in dataframe_merged_awt
    for index, row in dataframe_merged_awt.iterrows():
        begin_time = datetime.strptime(row['Begin'], "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(row['End'], "%Y-%m-%d %H:%M:%S")
        location = "Unknown"

        # Check for corresponding location in dataframe_locations
        for loc_index, loc_row in dataframe_locations.iterrows():
            loc_start = datetime.strptime(loc_row['Start_visit'], "%Y-%m-%d %H:%M:%S")
            loc_end = datetime.strptime(loc_row['End_visit'], "%Y-%m-%d %H:%M:%S")
            if loc_start <= begin_time <= loc_end or loc_start <= end_time <= loc_end or (begin_time <= loc_start and end_time >= loc_end):
                location = loc_row['Place_visited']
                break

        # Append the enriched data to the list
        enriched_rows.append({
            "App": row['App'],
            "Title": row['Title'],
            "Begin": begin_time,  # Convert to datetime object
            "End": end_time,      # Convert to datetime object
            "Location": location
        })

    # Create a new DataFrame with the enriched rows
    dataframe_merged_awt_with_locations = pd.DataFrame(enriched_rows)

    # Display the enriched DataFrame in Streamlit
    st.write("Enriched AWT data with locations:")
    st.write(dataframe_merged_awt_with_locations)

# Process data to create dataframe_days
if awt_uploaded_file is not None and google_maps_uploaded_files and survey_uploaded_file and oura_data_zip is not None:
    try:
        # Initialize a list to store the day-wise data
        day_rows = []

        # Get unique dates from Begin column of dataframe_merged_awt_with_locations
        unique_dates = pd.to_datetime(dataframe_merged_awt_with_locations['Begin']).dt.date.unique()

        # Iterate over each unique date
        for date in unique_dates:
            # Filter dataframe_merged_awt_with_locations for the current date
            filtered_data = dataframe_merged_awt_with_locations[pd.to_datetime(dataframe_merged_awt_with_locations['Begin']).dt.date == date]

            # Get start time (minimum Begin) and end time (maximum End) for the day
            start_time = filtered_data['Begin'].min()
            end_time = filtered_data['End'].max()

            started_day = start_time.hour + start_time.minute / 60.0
            ended_day = end_time.hour + end_time.minute / 60.0

            # Calculate total computer time for the day in hours (with two decimal places)
            total_computer_time = (pd.to_datetime(filtered_data['End']) - pd.to_datetime(filtered_data['Begin'])).sum().total_seconds() / 3600

            # Calculate number of computer breaks and total duration of breaks
            breaks_count = 0
            breaks_duration = 0

            # Iterate through rows to find breaks
            for index in range(len(filtered_data) - 1):
                current_end = pd.to_datetime(filtered_data.iloc[index]['End'])
                next_begin = pd.to_datetime(filtered_data.iloc[index + 1]['Begin'])
                if next_begin > current_end:
                    breaks_count += 1
                    breaks_duration += (next_begin - current_end).total_seconds()

            breaks_duration_hours = breaks_duration / 3600

            # Calculate percentage of time spent at home
            home_location = 'Drieboomlaan 273, 1624 BJ Hoorn, Nederland'
            home_time = filtered_data[filtered_data['Location'] == home_location]['End'].sub(
                filtered_data[filtered_data['Location'] == home_location]['Begin']).sum().total_seconds() / 3600
            percentage_at_home = (home_time / total_computer_time) if total_computer_time > 0 else 0

            # Calculate percentage of time spent at office
            office_location = 'Heidelberglaan 8, 3584 CS Utrecht, Nederland'
            office_time = filtered_data[filtered_data['Location'] == office_location]['End'].sub(
                filtered_data[filtered_data['Location'] == office_location]['Begin']).sum().total_seconds() / 3600
            percentage_at_office = (office_time / total_computer_time) if total_computer_time > 0 else 0

            # Check if date exists in survey data
            if date.strftime('%Y-%m-%d') in dataframe_survey['Date'].values:
                # Get survey data for the date
                survey_data = dataframe_survey[dataframe_survey['Date'] == date.strftime('%Y-%m-%d')].iloc[0]
                productivity = survey_data['Productivity'] / 5.0 if not pd.isna(survey_data['Productivity']) else None
                vigor = survey_data['Vigor'] / 7.0 if not pd.isna(survey_data['Vigor']) else None
                dedication = survey_data['Dedication'] / 7.0 if not pd.isna(survey_data['Dedication']) else None
                absorption = survey_data['Absorption'] / 7.0 if not pd.isna(survey_data['Absorption']) else None
            else:
                # Set survey data to None if not available
                productivity = None
                vigor = None
                dedication = None
                absorption = None

            # Calculate work engagement as average of vigor, dedication, absorption
            work_engagement = np.mean([vigor, dedication, absorption]) if not (pd.isna(vigor) or pd.isna(dedication) or pd.isna(absorption)) else None

            # Append the day data to the list
            day_rows.append({
                "Date": date,
                "Start_time": start_time,
                "Day_started": started_day,
                "End_time": end_time,
                "Day_ended": ended_day,
                "Total_computer_time": round(total_computer_time, 2),
                "Computer_breaks_num": breaks_count,
                "Computer_breaks_total_duration": round(breaks_duration_hours, 2),
                "Locations": "; ".join(filtered_data['Location'].unique()),
                "Percentage_at_home": round(percentage_at_home, 2),
                "Percentage_at_office": round(percentage_at_office, 2),
                "Productivity": productivity,
                "Vigor": vigor,
                "Dedication": dedication,
                "Absorption": absorption,
                "Work_engagement": work_engagement
            })

        # Create a new DataFrame with the day-wise data
        dataframe_days = pd.DataFrame(day_rows)

        # Convert 'day' column to datetime format in df_readiness and df_sleep
        df_readiness['day'] = pd.to_datetime(df_readiness['day'])
        df_sleep['day'] = pd.to_datetime(df_sleep['day'])

        # Ensure 'Date' column in dataframe_days is in datetime format
        dataframe_days['Date'] = pd.to_datetime(dataframe_days['Date'])

        # Concatenate df_readiness and df_sleep
        combined_data = pd.concat([df_readiness, df_sleep], ignore_index=True)

        # Aggregate combined_data by 'day'
        combined_grouped = combined_data.groupby('day').first().reset_index()

        # Convert 'day' column to datetime format in combined_grouped
        combined_grouped['day'] = pd.to_datetime(combined_grouped['day'])

        # Merge combined_grouped into dataframe_days
        dataframe_days = pd.merge(dataframe_days, combined_grouped, how='left', left_on='Date', right_on='day')

        # Calculate average scores for df_heart_rate
        average_scores = df_heart_rate.groupby('day').agg({
            'hrv': 'mean',
            'bpm': 'mean',
            'hrv_accuracy': 'mean'
        }).reset_index()

        # Convert 'day' column to datetime format in average_scores
        average_scores['day'] = pd.to_datetime(average_scores['day'])

        # Merge average scores into dataframe_days
        dataframe_days = pd.merge(dataframe_days, average_scores, how='left', left_on='Date', right_on='day')

        # Drop redundant 'day' columns after merge if needed
        if 'day' in dataframe_days.columns:
            dataframe_days.drop(['day'], axis=1, inplace=True)

        # Display the dataframe_days in Streamlit
        st.write("Final dataframe_days:")
        st.write(dataframe_days)

    except Exception as e:
        st.error(f"An error occurred while creating dataframe_days: {e}")
    
    # Filter out non-numeric columns
    numeric_columns = dataframe_days.select_dtypes(include=[np.number]).columns


    # Compute correlation matrix for numeric columns only
    correlation_matrix = dataframe_days[numeric_columns].corr()

    # Displaying the correlation matrix using streamlit
    st.write("## Correlation Matrix")
    st.write(correlation_matrix)

    # Function to interpret correlation scores
    def interpret_correlation_score(r, var1, var2):
        if r > 0.7:
            return f"Strong Positive Correlation: As `{var1}` increases, there is a strong tendency for `{var2}` to also increase, but not necessarily at a constant rate."
        elif r > 0.3:
            return f"Moderate Positive Correlation: As `{var1}` increases, there is a noticeable tendency for `{var2}` to also increase."
        elif r < -0.7:
            return f"Strong Negative Correlation: As `{var1}` increases, there is a strong tendency for `{var2}` to decrease at a consistent rate."
        elif r < -0.3:
            return f"Moderate Negative Correlation: As `{var1}` increases, there is a noticeable tendency for `{var2}` to decrease."
        else:
            return "No strong or moderate correlation."

    # Displaying a styled heatmap of the correlation matrix using HTML/CSS
    st.write("## Heatmap of Correlation Matrix")

    # Define a function to generate HTML for heatmap with column labels
    def heatmap_html(data):
        n = len(data)
        html = f'<table style="border-collapse: collapse; border: none; font-size: 12px;">'
        
        # Header row with rotated column labels
        html += '<tr>'
        html += '<td style="border: none;"></td>'  # Empty cell for row labels column
        for col in data.columns:
            html += f'<td style="border: none; padding: 8px; writing-mode: vertical-lr; transform: rotate(180deg);">{col}</td>'
        html += '</tr>'
        
        for i in range(n):
            html += '<tr>'
            html += f'<td style="border: none; padding: 8px; font-weight: bold;">{data.columns[i]}</td>'  # Row label
            for j in range(n):
                if j > i:  # Display only upper triangle of the matrix
                    value = data.iloc[i, j]
                    color = 'background-color: lightblue;' if i == j else f'background-color: rgba(100, 149, 237, {abs(value) / 1.5});'
                    html += f'<td style="border: none; padding: 8px; {color}">{value:.2f}</td>'
                else:
                    html += '<td style="border: none;"></td>'
            html += '</tr>'
        html += '</table>'
        return html

    # Display the heatmap using HTML
    st.write(heatmap_html(correlation_matrix), unsafe_allow_html=True)

    # Display interpretations of correlation coefficients
    st.write("## Interpretation of Correlation Scores")
    for i, col in enumerate(correlation_matrix.columns):
        for j, index in enumerate(correlation_matrix.columns):
            if j > i:  # Process only upper triangle of the matrix
                value = correlation_matrix.iloc[i, j]
                interpretation = interpret_correlation_score(value, col, index)
                if "No strong or moderate correlation." not in interpretation:
                    st.write(f"**Correlation between `{col}` and `{index}`:**")
                    st.write(interpretation)
                    # Generate scatterplot for strong and moderate positive and negative correlations
                    if abs(value) > 0.3:
                        chart_data = dataframe_days[[col, index]]
                        chart = alt.Chart(chart_data).mark_circle().encode(
                            x=col,
                            y=index,
                            tooltip=[col, index]
                        ).properties(
                            width=400,
                            height=300
                        )
                        st.altair_chart(chart)

