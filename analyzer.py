from flask import Flask, render_template, request, url_for
from werkzeug.utils import secure_filename
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO

# -------------------- APP SETUP --------------------
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "/tmp/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

ALLOWED_EXTENSIONS = {"csv", "xlsx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------- PLOT GENERATOR --------------------
def generate_plots(file_path):
    """Read CSV or Excel, convert numeric columns, generate plots, return base64 images"""
    if file_path.endswith(".csv"):
        df = pd.read_csv(file_path)
    elif file_path.endswith((".xls", ".xlsx")):
        df = pd.read_excel(file_path, sheet_name=0)
    else:
        raise ValueError("Unsupported file type")

    for col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="ignore")

    images = []
    numeric_cols = df.select_dtypes(include="number").columns

    for col in numeric_cols:
        # Histogram
        fig, ax = plt.subplots()
        sns.histplot(df[col], kde=True, ax=ax)
        ax.set_title(f"Distribution of {col}")
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode("utf-8")
        images.append(img_b64)
        plt.close(fig)

        # Boxplot
        fig, ax = plt.subplots()
        sns.boxplot(x=df[col], ax=ax)
        ax.set_title(f"Boxplot of {col}")
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode("utf-8")
        images.append(img_b64)
        plt.close(fig)

    if len(numeric_cols) > 1:
        fig, ax = plt.subplots(figsize=(8,6))
        sns.heatmap(df[numeric_cols].corr(), annot=True, cmap="coolwarm", ax=ax)
        ax.set_title("Correlation Heatmap")
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        img_b64 = base64.b64encode(buf.read()).decode("utf-8")
        images.append(img_b64)
        plt.close(fig)

    return images
