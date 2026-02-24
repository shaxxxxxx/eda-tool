from flask import Flask, render_template, request, redirect, url_for, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
import matplotlib
matplotlib.use("Agg") 
import matplotlib.pyplot as plt
import seaborn as sns
import base64
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
import os

# -------------------- APP SETUP --------------------
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = "uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("static", exist_ok=True)

ALLOWED_EXTENSIONS = {"csv", "xlsx"}

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

# -------------------- PLOT GENERATOR --------------------
def generate_plots(df):
    images = []
    numeric_cols = []

    # Detect numeric columns
    for col in df.columns:
        if df[col].dtype == "object":
            converted = pd.to_numeric(
                df[col].astype(str).str.replace(',', '').str.strip(),
                errors="coerce"
            )
            if converted.notna().sum() / len(converted) > 0.5:
                df[col] = converted
                numeric_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)

    # Limit to first 5 numeric columns
    numeric_cols = numeric_cols[:5]

    # Fill missing numeric values
    for col in numeric_cols:
        df[col].fillna(df[col].mean(), inplace=True)

    # Fill missing categorical values
    for col in df.select_dtypes(include="object").columns:
        if not df[col].empty:
            df[col].fillna(df[col].mode()[0], inplace=True)

    # Generate plots
    for col in numeric_cols:
        if df[col].dropna().empty:
            continue

        # Histogram
        fig, ax = plt.subplots(figsize=(4,3), dpi=80)
        sns.histplot(df[col], kde=True, ax=ax)
        ax.set_title(f"Distribution of {col}")
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        images.append(base64.b64encode(buf.read()).decode("utf-8"))
        plt.close(fig)

        # Boxplot
        fig, ax = plt.subplots(figsize=(4,3), dpi=80)
        sns.boxplot(x=df[col], ax=ax)
        ax.set_title(f"Boxplot of {col}")
        buf = BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        buf.seek(0)
        images.append(base64.b64encode(buf.read()).decode("utf-8"))
        plt.close(fig)

    # Correlation heatmap
    if len(numeric_cols) > 1:
        fig, ax = plt.subplots(figsize=(6,4), dpi=80)
        corr = df[numeric_cols].corr()
        if not corr.empty:
            sns.heatmap(corr, annot=True, cmap="coolwarm", ax=ax)
            ax.set_title("Correlation Heatmap")
            buf = BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight")
            buf.seek(0)
            images.append(base64.b64encode(buf.read()).decode("utf-8"))
            plt.close(fig)

    return images, df
# -------------------- PDF GENERATOR --------------------
def generate_pdf(df, plot_imgs):
    pdf_path = "/tmp/report.pdf"
    doc = SimpleDocTemplate(pdf_path, pagesize=letter)
    elements = []

    styles = getSampleStyleSheet()
    elements.append(Paragraph("EDA Report", styles["Title"]))
    elements.append(Spacer(1, 0.3 * inch))

    # Complete cleaned dataset table
    df = df.head(100)
    table_data = [df.columns.tolist()] + df.values.tolist()
    table = Table(table_data, repeatRows=1)
    elements.append(table)
    elements.append(Spacer(1, 0.5 * inch))

    # Add plots
    for img_b64 in plot_imgs:
        img_bytes = base64.b64decode(img_b64)
        img_buffer = BytesIO(img_bytes)
        img = Image(img_buffer, width=5*inch, height=3*inch)
        elements.append(img)
        elements.append(Spacer(1, 0.3 * inch))

    doc.build(elements)
    return send_file("/tmp/report.pdf", as_attachment=True)

# -------------------- ROUTES --------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return "No file uploaded"
    file = request.files["file"]
    if not file or not allowed_file(file.filename):
        return "Invalid file type"

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    # Read CSV or Excel
    if filename.endswith(".csv"):
        df = pd.read_csv(filepath, nrows=1000)
    else:
        df = pd.read_excel(filepath, sheet_name=0, nrows=1000)

    # Generate plots & clean data
    plot_imgs, cleaned_df = generate_plots(df)

    # Save cleaned CSV
    cleaned_csv_path = "/tmp/cleaned_data.csv"
    cleaned_df.to_csv(cleaned_csv_path, index=False)

    # Generate PDF
    return render_template(
    "report_template.html",
    table=df.head(20).to_html(classes="data", index=False),
    plots=plot_imgs,
    csv_file=cleaned_csv_path
)

# Route to download cleaned CSV
@app.route("/download_csv")
def download_csv():
    return send_file("/tmp/cleaned_data.csv", as_attachment=True)

@app.route("/download_pdf")
def download_pdf():
    csv_path = "static/cleaned_data.csv"

    # 🔒 Safety check
    if not os.path.exists(csv_path):
        return "No processed file found. Please upload first."

    df = pd.read_csv(csv_path)

    # Limit for safety
    df = df.head(300)

    plot_imgs, cleaned_df = generate_plots(df)

    pdf_path = generate_pdf(cleaned_df.head(100), plot_imgs)

    return send_file(pdf_path, as_attachment=True)

# Optional analyze route (redirect to /upload)
@app.route("/analyze", methods=["POST"])
def analyze():
    return redirect(url_for("upload_file"))

# -------------------- RUN APP --------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

