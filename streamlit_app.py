import numpy as np
import pandas as pd
import streamlit as st
import json
from io import StringIO
from datetime import datetime, timedelta
import re
import csv
import zipfile
import geopandas as gpd
from shapely.geometry import Point
from geopandas.tools import reverse_geocode

"""
# Let's analyse your Tockler and Oura data!
"""

# Sidebar for accepting input parameters
with st.sidebar:
    # Load AWT data
    st.header('Upload your data')
    st.markdown('**1. Tockler/AWT data**')
    awt_uploaded_file = st.file_uploader("Upload your Tockler data here. You can export your data by going to Tockler > Search > Set a time period > Export to CSV.", type='csv', key='awt')

    # Load daytime heart rate data
    # st.markdown('**2. Daytime heart rate**')
    # heart_rate_uploaded_file = st.file_uploader("Upload your heart rate data here. You can export your data by going to https://cloud.ouraring.com/profile > Export Data and clicking 'heart-rate.json'.", type='json', key='hr')

    # Load Daily sleep data
    # st.markdown('**3. Daily sleep**')
    # daily_sleep_uploaded_file = st.file_uploader("Upload your Daily sleep data here. You can export your data by going to https://cloud.ouraring.com/profile > Export Data and clicking 'daily-sleep.json'.", type='json', key='sleep')

    # Load Daily readiness data
    # st.markdown('**4. Daily readiness**')
    # daily_readiness_uploaded_file = st.file_uploader("Upload your Daily readiness data here. You can export your data by going to https://cloud.ouraring.com/profile > Export Data and clicking 'daily-readiness.json'.", type='json', key='readiness')

    # Load Location data
    # st.markdown('**5. Location data**')
    # location_uploaded_file = st.file_uploader("Upload your location data here. You can export your data by going to https://cloud.ouraring.com/profile > Export Data and clicking 'smoothed-location.json'.", type='json', key='location')

    # Load Oura data as ZIP
    st.markdown('**2. Oura data**')
    oura_data_zip = st.file_uploader("Upload your Oura data (ZIP file) here.", type='zip', key='oura')

# Function to process 'oura_daily-readiness' JSON data
def process_daily_readiness(data):
    readiness_data = []
    for entry in data["daily_readiness"]:
        contributors = entry["contributors"]
        day_data = {"day": entry["day"], "score": entry["score"], "temperature_deviation": entry.get("temperature_deviation", None)}
        day_data.update(contributors)
        readiness_data.append(day_data)
    return pd.DataFrame(readiness_data)

# Function to process 'oura_daily-sleep' JSON data
def process_daily_sleep(data):
    sleep_data = []
    for entry in data["daily_sleep"]:
        contributors = entry["contributors"]
        day_data = {"day": entry["day"], "score": entry["score"]}
        day_data.update(contributors)
        sleep_data.append(day_data)
    return pd.DataFrame(sleep_data)

# Function to process 'oura_heart-rate' JSON data
def process_heart_rate(data):
    return pd.DataFrame(data["heart_rate"])

# Function to process 'oura_smoothed-location' JSON data
def process_smoothed_location(data):
    return pd.DataFrame(data["smoothed_location"])

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
        st.write("Snippet of the raw AWT data:")
        st.write(dataframe_awt.head())

        # Remove rows where 'Begin' is empty
        dataframe_awt = dataframe_awt.dropna(subset=['Begin'])
        dataframe_awt = dataframe_awt[dataframe_awt['Begin'] != '']

        # Remove rows where 'Title' is 'NO_TITLE'
        dataframe_awt = dataframe_awt[dataframe_awt['Title'] != 'NO_TITLE']

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
        df_location = None

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
                elif file_name.startswith("oura_smoothed-location"):
                    df_location = process_smoothed_location(json_data)

        # Display dataframes
        if df_readiness is not None:
            st.subheader("Daily Readiness Data")
            st.dataframe(df_readiness)
        
        if df_sleep is not None:
            st.subheader("Daily Sleep Data")
            st.dataframe(df_sleep)
        
        if df_heart_rate is not None:
            st.subheader("Heart Rate Data")
            st.dataframe(df_heart_rate)
        
        if df_location is not None:
            st.subheader("Smoothed Location Data")
            st.dataframe(df_location)