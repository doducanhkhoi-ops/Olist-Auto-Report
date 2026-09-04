import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import mysql.connector
from google import genai
import traceback
import sys

def get_data_from_db():
    print("Connecting to Aiven MySQL...", flush=True)
    conn = mysql.connector.connect(
        host=os.environ['DB_HOST'],
        port=18064,
        user=os.environ['DB_USER'],
        password=os.environ['DB_PASS'],
        database="defaultdb"
    )
    cursor = conn.cursor(dictionary=True)
    
    query = """
    SELECT r.review_score, r.review_comment_message, p.product_category_name, i.price, i.freight_value
    FROM reviews r
    JOIN order_items i ON r.order_id = i.order_id
    JOIN products p ON i.product_id = p.product_id
    WHERE r.review_score IN (1, 2) AND r.review_comment_message IS NOT NULL
    LIMIT 30;
    """
    cursor.execute(query)
    data = cursor.fetchall()
    conn.close()
    return data

def analyze_with_gemini(data):
    print("Analyzing data with Gemini...", flush=True)
    client = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
    
    prompt = f"""
    Bạn là một Data Analyst chuyên nghiệp. Dưới đây là dữ liệu 30 đánh giá tệ (1-2 sao) của khách hàng từ database e-commerce Olist:
    {data}
    
    Nhiệm vụ của bạn:
    1. Đọc và hiểu các phàn nàn của khách hàng.
    2. Tìm ra Insight (điểm cốt lõi, vấn đề lớn nhất) từ dữ liệu này.
    3. Viết 1 báo cáo phân tích sâu dành cho sinh viên năm 3 đọc.
    4. Trình bày báo cáo hoàn toàn bằng mã HTML. KHÔNG bọc mã trong markdown ```html. Hãy trả về HTML thuần túy.
    """
    
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
    )
    return response.text

def send_email(html_content):
    print("Sending email...", flush=True)
    msg = MIMEMultipart()
    msg['From'] = os.environ['EMAIL_USER']
    msg['To'] = os.environ['EMAIL_USER']
    msg['Subject'] = "🚀 [Olist Database] Báo cáo Insight Phân tích Tự động"
    
    if html_content.startswith("```html"):
        html_content = html_content[7:]
    if html_content.endswith("```"):
        html_content = html_content[:-3]

    msg.attach(MIMEText(html_content, 'html'))
    
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(os.environ['EMAIL_USER'], os.environ['EMAIL_PASS'])
    server.send_message(msg)
    server.quit()
    print("Email sent successfully!", flush=True)

if __name__ == "__main__":
    try:
        data = get_data_from_db()
        report = analyze_with_gemini(data)
        send_email(report)
        print("Done!", flush=True)
    except Exception as e:
        print("CRITICAL ERROR ENCOUNTERED:", flush=True)
        traceback.print_exc()
        sys.exit(1)
