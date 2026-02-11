import streamlit as st
import pdfplumber
from pdf2image import convert_from_bytes
from PIL import Image
import io
import json
import re
import os
from openai import OpenAI
import platform
import pytesseract

if platform.system() == "Windows":
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
else:
    # Linux (Streamlit Cloud, Render etc.)
    pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
# ---------------- CONFIG ---------------- #

st.set_page_config(
    page_title="Research Portal – Earnings Call Tool",
    layout="wide"
)

# ---------------- API KEY ---------------- #

# For local use:
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

if not OPENROUTER_API_KEY:
    st.error("OpenRouter API key not found. Set OPENROUTER_API_KEY in environment.")
    st.stop()

client = OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url="https://openrouter.ai/api/v1",
)

# ---------------- FUNCTIONS ---------------- #

def extract_text(uploaded_file):
    file_bytes = uploaded_file.read()
    uploaded_file.seek(0)

    text = ""

    # Try normal PDF extraction
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
    except:
        pass

    # OCR fallback if no text found
    if not text.strip():
        st.info("🔍 Using OCR fallback...")
        try:
            images = convert_from_bytes(file_bytes)
            for img in images:
                text += pytesseract.image_to_string(img)
        except Exception as e:
            st.error(f"OCR failed: {e}")
            return None

    return text


def analyze_transcript(text):
    prompt = f"""
You are an equity research analyst.

STRICT RULES:
- Use only information explicitly mentioned.
- Do NOT assume or invent data.
- If something is not mentioned, return: "Not mentioned in transcript".
- Return ONLY raw JSON.
- Do NOT wrap JSON in markdown.
- No commentary.

JSON format:
{{
  "management_tone": "",
  "confidence_level": "",
  "key_positives": [],
  "key_concerns": [],
  "forward_guidance": "",
  "capacity_utilization": "",
  "growth_initiatives": []
}}

Transcript:
{text[:8000]}
"""

    response = client.chat.completions.create(
        model="mistralai/mistral-7b-instruct",
        temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_output = response.choices[0].message.content

    # Extract JSON safely
    match = re.search(r"\{.*\}", raw_output, re.DOTALL)
    if not match:
        return {"error": "Model did not return structured JSON"}

    try:
        structured = json.loads(match.group())
        return structured
    except:
        return {"error": "Failed to parse model JSON output"}


# ---------------- UI ---------------- #

st.markdown("""
<style>
.main-title {
    font-size: 42px;
    font-weight: bold;
}
.subtitle {
    font-size: 18px;
    color: gray;
}
.section-title {
    margin-top: 25px;
}
.result-card {
    background-color: #111827;
    padding: 25px;
    border-radius: 12px;
}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-title">📊 Research Portal – Earnings Call Tool</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Upload an earnings call transcript (PDF) and receive structured analyst-grade insights.</div>', unsafe_allow_html=True)

st.write("")
uploaded_file = st.file_uploader("Upload Transcript PDF", type=["pdf"])

if uploaded_file:
    if st.button("🚀 Run Earnings Call Analysis"):
        with st.spinner("Processing transcript... This may take 20–30 seconds..."):
            text = extract_text(uploaded_file)

            if not text:
                st.error("Unable to extract text from PDF.")
                st.stop()

            result = analyze_transcript(text)

        # Display result
        if "error" in result:
            st.error(result["error"])
        else:
            st.success("Analysis Complete ✅")

            st.markdown('<div class="result-card">', unsafe_allow_html=True)

            col1, col2 = st.columns(2)
            col1.metric("Management Tone", result["management_tone"])
            col2.metric("Confidence Level", result["confidence_level"])

            st.markdown("### Key Positives")
            for item in result["key_positives"]:
                st.write(f"- {item}")

            st.markdown("### Key Concerns")
            for item in result["key_concerns"]:
                st.write(f"- {item}")

            st.markdown("### Forward Guidance")
            st.write(result["forward_guidance"])

            st.markdown("### Capacity Utilization")
            st.write(result["capacity_utilization"])

            st.markdown("### Growth Initiatives")
            for item in result["growth_initiatives"]:
                st.write(f"- {item}")

            st.markdown('</div>', unsafe_allow_html=True)
