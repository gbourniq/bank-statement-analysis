import logging
import os
import pickle
import re
import time

import numpy as np
import pandas as pd
import pytesseract
from flask import (Flask, Response, redirect, render_template, request,
                   send_from_directory, url_for)

from pdf2image import convert_from_path
from pdf2image.exceptions import (PDFInfoNotInstalledError, PDFPageCountError,
                                  PDFSyntaxError)
from PIL import Image
from sklearn.feature_extraction.text import CountVectorizer

from parameters import (database, dbo_table, driver, label_mapping, password,
                        server, username)


# Decode category_id to category name
def label_decoder(value):
    """
    Input: Category index (number)
    Output: Category as a string
    """
    for key, dictvalue in label_mapping.items():
        if value == dictvalue:
            return key
    return None

# Predict category for new/unseen references
def predictml_category(description, ML_FOLDER):
    """
    Takes a transaction source as an input, and predicts a transaction category using the loaded_model
    Returns predicted category index and level of confidence
    """
    
    # load the model from disk
    loaded_model = pickle.load(open(ML_FOLDER + '/finalised_model.sav', 'rb'))
    # Load vocabulary
    sentences_train = np.load(ML_FOLDER + "/sentences_train.npy")

    vectorizer = CountVectorizer()
    vectorizer.fit(sentences_train)
    vectorizer.vocabulary_
    vectorizer.transform(sentences_train).toarray()
    
    label_nparray = loaded_model.predict(vectorizer.transform([description]))
    label_proba = np.max(loaded_model.predict_proba(vectorizer.transform([description])))
    label_proba = np.round(label_proba, 2)
    
    strlabel = np.array2string(label_nparray, precision=2, separator=',', suppress_small=True)
    strlabel = label_decoder(strlabel[1:-1])
    
    return [strlabel, label_proba]

def predict_category(description, ML_FOLDER):
    """
    Predict a transaction category using the predictml_category function
    If the level of confidence is below the threshold, the transaction is categorised as "Other"
    """

    if predictml_category(description, ML_FOLDER)[1] > 0.3:
        return predictml_category(description, ML_FOLDER)[0]
    else:
        return "Other"

def read_image(image_path):
    """
    Input: Image path
    Output: Extracted text from Tesseract OCR
    """

    # Comment line below if running app with Docker
    #pytesseract.pytesseract.tesseract_cmd = TESSERACT_FOLDER + r"/tesseract.exe"
    fulltext = pytesseract.image_to_string(Image.open(image_path), lang='eng')
    return fulltext

# Takes a pdf path and return list of images path
def pdf_to_images(pdf_path, UPLOAD_FOLDER):
    """
    Input: Pdf path
    Output: Extracted text
    """

    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    images = convert_from_path(pdf_path, 200)
    PageNumber = 0
    saved_images = []
    for image in images:
        PageNumber += 1
        image_path = UPLOAD_FOLDER + pdf_name + "_" + str(PageNumber) + ".jpg"
        image.save(image_path, "JPEG", quality=10)
        saved_images.append(image_path)

    return saved_images


def allowed_file(filename):
    """
    Check that uploaded files are either pdf or xlsx
    """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in set(['pdf', 'xlsx'])

def clean_uploadfolder(UPLOAD_FOLDER):
    """
    Delete the content of the upload folder
    """
    for filename in os.listdir(UPLOAD_FOLDER):
        os.remove(UPLOAD_FOLDER + "/" + filename)

def filter_ref_col(reference):
    """
    Filter out meaningless characters from the transaction line
    This should reflect the data processing steps required for a specific dataset
    """
    if re.search(r'(\d+/\d+/\d+)', reference):
        match = re.search(r'(\d+/\d+/\d+)', reference).group(1)
        reference = reference.replace(match, "")
    if re.search(r'(\d{4,10})', reference):
        match = re.search(r'(\d{4,10})', reference).group(1)
        reference = reference.replace(match, "")
    for char in reference:
        if char in "-?!/;:_":
            reference = reference.replace(char, "")
    return reference

def extract_amount(reference):
    """
    Input: Transaction line containing transaction value at the end of the string
    Return: Extracted transaction value (0,00 format)
    """

    if "." in reference:
        reference = reference.replace(".", " ")
    if reference[-5] == " ":
        # The line ends with the following transaction value " x,xx"
        return reference[-5:]
    elif reference[-6] == " ":
        # Ends with the following " xx,xx"
        return reference[-6:]
    elif reference[-7] == " ":
        # Ends with the following " xxx,xx"
        if re.search(r'(\b(\d){1,2}.?\d{3},[0-9]{2})', reference):
            # Ends with the following "x xxx,xx" ro "xx xxx,xx"
            match = re.search(r'(\b(\d){1,2}.?\d{1,3},[0-9]{2})', reference).group(1)
            return match
        else:
            # Ends with the following "text xxx,xx"
            return reference[-6:]

def text_to_df(UPLOAD_FOLDER, ML_FOLDER):
    """
    Loop through UPLOAD folder for txt files, extract relevant transaction details and create a dataframe
    """

    dates = []
    values = []
    references = []
    time.sleep(0.5)
    logging.info("Formating Table...")
 
    # Return dates, values and ref lists from all text files
    for filename in os.listdir(UPLOAD_FOLDER):
        if filename.endswith(".txt"): 
            year = filename[-12:-8]
            month = filename[-8:-6]
            day = filename[-6:-4]

            with open(UPLOAD_FOLDER + "/" + filename, "r", encoding="utf-8") as f:
                text = f.read()
            start = 'SOLDE PRECEDENT'
            stop = 'NOUVEAU SOLDE'
            cut_text = text[(text.index(start)+len(start)):text.index(stop)]

            for line in cut_text.splitlines()[1:-1]:
                if "," in line[-3:] and re.search(r'^(\d\d/\d\d)', line):
                    # If month is 12 in a January statement > display the previous year
                    if line[3:5] == "12" and month == "01":
                        dates.append(line[:5] + "/" + str(int(year)-1))
                    else:
                        dates.append(line[:5] + "/" + year)
                    # Trying to extract transaction value
                    try:
                        filtered_ref = filter_ref_col(line[6:])
                        value = extract_amount(filtered_ref)
                        values.append(str(value).strip())
                    except Exception as e:
                        logging.error("Could not extract value data. Replacing with dummy value. {}".format(str(e)))
                        values.append("0,00")
                    # Trying to extract transaction source
                    try:
                        filtered_ref = filtered_ref.replace(value, "")
                        references.append(str(filtered_ref).strip())
                    except Exception as e:
                        logging.error("Could not extract reference data. Replacing with dummy value. {}".format(str(e)))
                        references.append("ERROR")

    # Create Dataframe
    pd_dict = {
        'date' : dates,
        'value' : values,
        'reference' : references
    }
    df = pd.DataFrame(pd_dict)

    # Add columns
    df['category'] = 'category'
    df['id'] = 'id'

    # Format Date Column
    df["date"] = pd.to_datetime(df["date"], format='%d/%m/%Y', errors='coerce')

    # Filter out rows with invalid date
    df = df[~df['date'].isnull()]

    for index, row in df.iterrows():
        # Generate Primary Key
        entry_number = index + 1
        if entry_number < 10:
            entry_number = "0" + str(entry_number)
        else:
            entry_number = str(entry_number)
        df.loc[index, 'id'] = year + month + entry_number

        # Filter reference column
        for char in df.loc[index, 'reference']:
            if char in ",' ":
                df.loc[index, 'reference'] = df.loc[index, 'reference'].replace(char,"")
    
    # Assign Categories
    for index, row in df.iterrows():
        df.loc[index, 'category'] = predict_category(df.loc[index, 'reference'], ML_FOLDER)

    # Order columns
    cols = ['id', 'date', 'value', 'category', 'reference']
    df = df[cols]
    df.rename(columns={'id': 'ID', 'date': 'Date', 'value':'Value', 'category':'Category', 'reference':'Reference'}, inplace=True)
    time.sleep(0.5)
    logging.info("Table successfully created.")

    # Change columns type
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Value'] = pd.to_numeric(df['Value'], errors='coerce')

    return df
