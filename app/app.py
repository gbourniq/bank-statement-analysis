import logging
import os
import re
import urllib.parse

import pandas as pd
from flask import (Flask, Response, redirect, render_template, request,
                   send_from_directory, url_for)
from flask_bootstrap import Bootstrap
from flask_login import (LoginManager, UserMixin, current_user, login_required,
                         login_user, logout_user)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from wtforms import BooleanField, PasswordField, StringField
from wtforms.validators import Email, InputRequired, Length

import pyodbc
from functions import *
from parameters import (database, dbo_table, driver, label_mapping, password,
                        server, username)

# DATABASE URI: 
params = urllib.parse.quote_plus("DRIVER={};SERVER={};DATABASE={};UID={};PWD={}".format(
        driver, server, database, username, password
    )
)

# FLASK APP INIT
app = Flask(__name__)
app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = "mssql+pyodbc:///?odbc_connect=%s" % params
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True

# FLASK APP EXTENSIONS
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
bootstrap = Bootstrap(app)
login_manager.login_view = 'login'

# USER CLASS DEFINITION
class Users(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(15), unique=True)
    email = db.Column(db.String(50), unique=True)
    password = db.Column(db.String(80))

@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

# FLASK FORM CLASSES
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])
    remember = BooleanField('Remember Me')

class NewPwdForm(FlaskForm):
    password = PasswordField('Old Password', validators=[InputRequired(), Length(min=8, max=80)])
    new_pwd = PasswordField('New Password', validators=[InputRequired(), Length(min=8, max=80)])
    new_pwd_confirmation = PasswordField('New Password Confirmation', validators=[InputRequired(), Length(min=8, max=80)])

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[InputRequired(), Email(message='Invalid Email'), Length(max=50)])
    username = StringField('Username', validators=[InputRequired(), Length(min=4, max=15)])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=80)])

# LOGGING SETUP   
logging.basicConfig(filename='logfile.txt', level = logging.INFO)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('PIL.PngImagePlugin').setLevel(logging.WARNING)

# GLOBAL VARIABLES
UPLOAD_FOLDER = os.path.dirname(os.path.realpath(__file__)) + "/uploads/"
DOWNLOAD_FOLDER = os.path.dirname(os.path.realpath(__file__)) + "/downloads/"
ML_FOLDER = os.path.dirname(os.path.realpath(__file__)) + "/ml/"

# ROUTES
@app.route("/", methods = ["GET", "POST"])
def start():
    return redirect("/home")

@app.route("/home", methods = ["GET", "POST"])
@login_required
def home():
    return render_template("home.html", name=current_user.username)

@app.route('/login', methods = ["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        try:
            user = Users.query.filter_by(username=form.username.data).first()
            if user:
                if check_password_hash(user.password, form.password.data):
                    login_user(user, remember=form.remember.data)
                    return redirect(url_for('home'))

            return render_template('signin.html', form=form, err = "Invalid username or password")
        
        except Exception as e:
            logging.critical("The following error occured when logging in: {}".format(str(e)))
            return render_template('signin.html', form=form, err = "An error has occured. See logs for details.")

    return render_template('signin.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()

    if form.validate_on_submit():
        try:
            return render_template('signup.html', form=form, err = "Feature disabled for demo purposes")
            #hashed_password = generate_password_hash(form.password.data, method='sha256')
            #new_user = Users(username=form.username.data, email=form.email.data, password=hashed_password)
            #db.session.add(new_user)
            #db.session.commit()
            #return render_template('signup.html', form=form, err = "New user has been created!")
        
        except Exception as e:
            logging.critical("The following error occured when signing up: {}".format(str(e)))
            return render_template('signup.html', form=form, err = "An error has occured. See logs for details.")

    return render_template('signup.html', form=form)

@app.route('/account', methods=['GET', 'POST'])
@login_required
def update_pwd():
    form = NewPwdForm()

    if form.validate_on_submit():

        try:
            user = Users.query.filter_by(username=current_user.username).first()
            if user:
                if check_password_hash(user.password, form.password.data):
                    if form.new_pwd.data == form.new_pwd_confirmation.data:
                        return render_template('newpwd.html', form=form, err = "Feature disabled for demo purposes")
                        #hashed_password = generate_password_hash(form.new_pwd.data, method='sha256')
                        #user.password = hashed_password
                        #db.session.commit()
                        #return render_template('newpwd.html', form=form, err = "Password successfully updated!")
                    else:
                        return render_template('newpwd.html', form=form, err = "Password confirmation does not match")
        
        except Exception as e:
            logging.critical("The following error occured when changing password: {}".format(str(e)))
            return render_template('newpwd.html', form=form, err = "An error has occured. See logs for details.")
                
        return render_template('newpwd.html', form=form, err = "Invalid username or password")

    return render_template('newpwd.html', form=form, err = "")

@app.route("/spendingview", methods = ["GET", "POST"])
@login_required
def spendingview():
    return render_template("pbi_chartspending.html")

@app.route("/incomeview", methods = ["GET", "POST"])
@login_required
def incomeview():
    return render_template("pbi_chartincome.html")

@app.route("/tableview", methods = ["GET", "POST"])
@login_required
def tableview():
    return render_template("pbi_tableview.html")

@app.route("/upload", methods = ["GET", "POST"])
@login_required
def upload():
    
    try:
        clean_uploadfolder(UPLOAD_FOLDER)
    except Exception as e:
        logging.debug("Error when cleaning up upload folder {}".format(str(e)))

    if request.method == 'POST':
        if 'file' in request.files:
            file = request.files['file']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)

                if filename.split(".")[1].lower() == "pdf":
                    if not re.match('^[0-9]{8}$',filename[-12:].split(".")[0]):
                        logging.critical("Invalid pdf name. Expected the following structure: RELEVES_MR SURNAME FIRSTNAME_20140220.pdf")
                        return render_template("upload.html", stage = "fileselection")
                    pdf_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(pdf_path)
                    return render_template("upload.html", stage = "pdfprocessing")

                elif filename.split(".")[1].lower() == "xlsx":
                    excel_path = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(excel_path)
                    logging.info("Excel file uploaded")
                    try:
                        # Write to Output table Excel
                        df = pd.read_excel(excel_path)
                        writer = pd.ExcelWriter(UPLOAD_FOLDER + "/output_table.xlsx")
                        df.to_excel(writer, 'Sheet1', index=False)
                        writer.save()
                        return render_template("upload.html", dataframe = df.to_html(classes="jumbotron_table"), stage = "dfview")
                    except Exception as e:
                        logging.critical("Error occured when processing xlsx file: {}".format(str(e)))

    return render_template("upload.html", stage = "fileselection") 

@app.route('/upload/<path:filename>', methods=['GET', 'POST'])
@login_required
def download_excelouput(filename):
    try:
        return send_from_directory(directory=UPLOAD_FOLDER, filename=filename, as_attachment=True)
    except Exception as e:
        logging.critical("Exception when downloading file: {}".format(str(e)))
        return render_template("upload.html", stage = "fileselection")

@app.route('/download/<path:filename>', methods=['GET', 'POST'])
@login_required
def download_sample(filename):
    try:
        return send_from_directory(directory=DOWNLOAD_FOLDER, filename=filename, as_attachment=True)
    except Exception as e:
        logging.critical("Exception when downloading file: {}".format(str(e)))
        return render_template("upload.html", stage = "fileselection")

@app.route('/dfview', methods=['GET', 'POST'])
@login_required
def dfview():
    outputfilepath = UPLOAD_FOLDER + "/" + "output_table.xlsx"
    df = pd.read_excel(outputfilepath, encoding="utf-8")

    return render_template("upload.html", dataframe = df.to_html(classes="jumbotron_table"), stage="dfview")

@app.route('/updateconfirmation', methods=['GET', 'POST'])
@login_required
def updateconfirmation():
    outputfilepath = UPLOAD_FOLDER + "/" + "output_table.xlsx"
    df = pd.read_excel(outputfilepath, encoding="utf-8")

    return render_template("upload.html", dataframe = df.to_html(classes="jumbotron_table"), stage = "updateconfirmation")
    
@app.route('/updatingdb', methods=['GET', 'POST'])
@login_required
def updatingdb():
    outputfilepath = UPLOAD_FOLDER + "/" + "output_table.xlsx"
    df = pd.read_excel(outputfilepath, encoding="utf-8")

    return render_template("upload.html", dataframe = df.to_html(classes="jumbotron_table"), stage = "updatingdb")

@app.route('/progress_pdfprocessing')
@login_required
def progress_pdfprocessing():
    def generate():
        logging.info("Starting...")
        try:
            for file_path in os.listdir(UPLOAD_FOLDER):
                if file_path.endswith(".pdf"):
                    pdf_path = UPLOAD_FOLDER + "/" + file_path
                    logging.info("pdf path: {}".format(pdf_path))
        except Exception as e:
            logging.critical("Pdf path could not be found : {}".format(str(e)))
            return render_template("upload.html", stage = "uploadfailure")

        try:
            # Takes a pdf path and save extracted text to text files in the UPLOAD folder
            images = pdf_to_images(pdf_path, UPLOAD_FOLDER)

            progress = 0
            int_progress = 0
            total_loop_count = len(images) + 1
            last_step = 100
            step = float(last_step / total_loop_count)
            counter = 0
            ocr_text = ""
            progress += step
            int_progress = int(progress)
            yield "data:" + str(int_progress) + "\n\n"

            logging.info("Processed 0/{} page(s)...".format(len(images)))
            for image in images:
                counter += 1
                ocr_text = ocr_text + "\n" + read_image(image)

                int_progress = int(progress)
                if int_progress <= last_step:
                    yield "data:" + str(int_progress) + "\n\n"
                    logging.info("Processed {}/{} page(s)...".format(str(counter), len(images)))
                    progress += step

                os.remove(image)

            with open(UPLOAD_FOLDER + os.path.basename(pdf_path).split(".")[0] + ".txt", "w", encoding="utf-8") as text_file:
                text_file.write(ocr_text)
        except Exception as e:
            logging.critical("Error occurred while atempting to convert pdf to txt : {}".format(str(e)))

        try:
            df = text_to_df(UPLOAD_FOLDER, ML_FOLDER)
        except Exception as e:
            logging.critical("Error occurred while atempting to generate df from txt : {}".format(str(e)))

        try:
            # Write to Excel
            writer = pd.ExcelWriter(UPLOAD_FOLDER + "/output_table.xlsx")
            df.to_excel(writer, 'Sheet1', index=False)
            writer.save()
            logging.info("Pdf file saved")
        except Exception as e:
            logging.critical("Error occurred while atempting to save df as .xlsx : {}".format(str(e)))

        int_progress = 100
        yield "data:" + str(int_progress) + "\n\n"

    return Response(generate(), mimetype= 'text/event-stream')

@app.route('/progress_updatingdb')
@login_required
def progress_updatingdb():
    def generate():
        progress = 0
        int_progress = 0
        succeeded = 0
        failed = 0

        try:
            outputfilepath = UPLOAD_FOLDER + "/" + "output_table.xlsx"
            df = pd.read_excel(outputfilepath, encoding="utf-8")
            total_rows = int(df.shape[0]) - 1
            last_step = 100
            step = float(last_step / total_rows)
            print(str(step))

            logging.info("Connecting to DB")
            cnxn = pyodbc.connect('DRIVER={};SERVER={};PORT=1433;DATABASE={};UID={};PWD={}'.format(
                    driver, server, database, username, password
                )
            )

            cursor = cnxn.cursor()
        except Exception as e:
            logging.critical("Could not connect to database : {}".format(str(e)))
            return render_template("upload.html", stage = "uploadfailure")

        for index, row in df.iterrows():
            try:
                qStr = "INSERT INTO {}([ID],[Date],[Value],[Category],[Reference]) VALUES ('{}','{}','{}','{}','{}')".format(
                    dbo_table, str(row['ID']), row['Date'], row['Value'],row['Category'],row['Reference']
                    )
                cursor.execute(qStr)
                cnxn.commit()
                succeeded += 1
            except Exception as e:
                logging.debug("SQL Insert failed: {}".format(str(e)))
                failed += 1
            finally:
                if index == total_rows:
                    progress = last_step
                int_progress = int(progress)
                if int_progress <= last_step:
                    yield "data:" + str(int_progress) + "\n\n"
                    progress += step

        logging.info("Closing DB connection")
        cursor.close()
        cnxn.close()

        logging.info("{} successful transactions.".format(str(succeeded)))
        logging.info("{} failed transactions.".format(str(failed)))

        # save number of failed/succeeded SQL transations
        with open(UPLOAD_FOLDER + "/sql_results.txt", "w") as sql_results:
            sql_results.write(str(succeeded) + "\n")
            sql_results.write(str(failed))

    return Response(generate(), mimetype= 'text/event-stream')

@app.route("/success", methods = ["GET", "POST"])
@login_required
def success():
    with open(UPLOAD_FOLDER + "/sql_results.txt") as f:
        content = f.readlines()
    content = [x.strip() for x in content]

    return render_template("success.html", success = content[0], failure = content[1])


if __name__ == "__main__":
    app.run(debug=True)
