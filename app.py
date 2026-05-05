from flask import Flask, render_template, request
import pandas as pd
import string
import nltk
import sqlite3
import datetime
import os

from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# -----------------------------
# Flask App Setup
# -----------------------------
app = Flask(__name__)

# -----------------------------
# NLTK & ML Preparation
# -----------------------------
nltk.download('stopwords')
nltk.download('wordnet')
nltk.download('punkt')

lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words('english'))

def preprocess(text):
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    words = text.split()
    words = [lemmatizer.lemmatize(word) for word in words if word not in stop_words]
    return " ".join(words)

# -----------------------------
# Model Training (Production Tip: Load via Joblib instead)
# -----------------------------
# Ensure your CSV is in the same folder as this script
if os.path.exists("dataset for chatbot.csv"):
    df = pd.read_csv("dataset for chatbot.csv")
    df['processed_text'] = df['text'].apply(preprocess)

    vectorizer = TfidfVectorizer()
    X = vectorizer.fit_transform(df['processed_text'])
    y = df['intent']

    model = LogisticRegression(max_iter=200)
    model.fit(X, y)
else:
    print("Error: 'dataset for chatbot.csv' not found!")

# -----------------------------
# Database Setup
# -----------------------------
def get_db_connection():
    conn = sqlite3.connect("chatbot_logs.db", check_same_thread=False)
    return conn

conn = get_db_connection()
cursor = conn.cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    user_input TEXT,
    intent TEXT,
    confidence REAL
)
""")
conn.commit()

# -----------------------------
# Response Mapping
# -----------------------------
responses = {
    "admissions": "Admissions are based on entrance exams and merit. Apply via the official college portal.",
    "fees": "The tuition fee is approximately ₹1,00,000 per year.",
    "exams": "Exams are conducted at the end of each semester. Timetable will be shared before exams.",
    "hostel": "Hostel facilities include food, WiFi, security, and laundry services.",
    "library": "Library is open from 8 AM to 8 PM with access to digital and physical resources.",
    "timetable": "Timetable will be shared one week before exams.",
    "placements": "Top companies visit campus every year with good placement opportunities.",
    "faculty": "Faculty members are highly qualified and experienced in their domains.",
    "courses": "We offer BTech, MTech, and other specialized programs.",
    "transport": "College buses are available across major city routes.",
    "campus": "Campus has modern infrastructure, labs, sports facilities, and WiFi."
}

# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/get", methods=["POST"])
def chatbot():
    user_input = request.form["msg"]
    text_clean = user_input.lower()
    
    response = ""
    intent = "unknown"
    confidence = 1.0  # Default for rule-based

    # 1. RULE-BASED PRIORITY
    if "hostel" in text_clean and "fee" in text_clean:
        intent = "hostel_fees"
        response = "Hostel fee is approximately ₹60,000 per year including food."
    elif "fee" in text_clean:
        intent = "fees"
        response = responses["fees"]
    elif "timetable" in text_clean or "time table" in text_clean:
        intent = "timetable"
        response = responses["timetable"]
    
    # 2. ML MODEL (If no rule-based response was found)
    else:
        processed = preprocess(user_input)
        vector = vectorizer.transform([processed])
        probs = model.predict_proba(vector)
        confidence = float(max(probs[0]))

        if confidence < 0.4:
            intent = "unclear"
            response = "I'm not quite sure. Try asking about Admissions, Fees, or Hostel."
        else:
            intent = model.predict(vector)[0]
            response = responses.get(intent, "I'm sorry, I don't have information on that yet.")

    # 3. LOGGING (Ensures every chat is saved)
    try:
        cursor.execute(
            "INSERT INTO logs (timestamp, user_input, intent, confidence) VALUES (?, ?, ?, ?)",
            (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), user_input, intent, confidence)
        )
        conn.commit()
    except Exception as e:
        print(f"Logging Error: {e}")

    return f"{response} (Confidence: {round(confidence, 2)})"

if __name__ == "__main__":
    app.run(debug=True)