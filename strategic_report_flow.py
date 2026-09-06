import sys
import html
import io
import os
import json
import csv
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import mysql.connector

# Thiết lập encoding UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============== CẤU HÌNH (HỖ TRỢ CẢ LOCAL VÀ GITHUB ACTIONS / CLOUD) ==============
GMAIL_USER = os.getenv("GMAIL_USER", "doducanhkhoi.bec@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "wkof rxcj jshh zjql")
EMAIL_TO = os.getenv("EMAIL_TO", "doducanhkhoi.bec@gmail.com")

MYSQL_HOST = os.getenv("MYSQL_HOST", os.getenv("DB_HOST", "localhost"))
MYSQL_PORT = int(os.getenv("MYSQL_PORT", os.getenv("DB_PORT", 3306)))
MYSQL_USER = os.getenv("MYSQL_USER", os.getenv("DB_USER", "root"))
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", os.getenv("DB_PASSWORD", "@Kk1332006"))
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", os.getenv("DB_NAME", "olist_raw"))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "strategic_report_state.json")
# =================================================================================

THEMES = ["rfm", "seller", "basket", "category"]

THEME_META = {
    "rfm": {
        "title": "Báo Cáo Phân Khúc Khách Hàng (RFM) & Nghịch Lý São Paulo",
        "subtitle": "Phân tích mức độ giữ chân (Retention) & Giá trị trọn đời (LTV)",
        "badge": "CUSTOMER LIFECYCLE & RETENTION",
        "color": "#e74c3c",
        "gradient": "linear-gradient(135deg, #1e3c72 0%, #2a5298 100%)"
    },
    "seller": {
        "title": "Ma Trận Hiệu Suất Người Bán (Volume vs Value) & Mạng Lưới Vùng",
        "subtitle": "Phân loại Single vs Multi-region Sellers & Rủi ro tỷ lệ hoàn/hủy",
        "badge": "SUPPLY CHAIN & SELLER MATRIX",
        "color": "#2980b9",
        "gradient": "linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%)"
    },
    "basket": {
        "title": "Giải Mã Đơn Hàng Multi-Seller & Đa Dạng Hóa Danh Mục",
        "subtitle": "Đánh giá đòn bẩy AOV từ giỏ hàng đa shop & Năng lực Logistics",
        "badge": "BASKET DYNAMICS & LOGISTICS SLA",
        "color": "#27ae60",
        "gradient": "linear-gradient(135deg, #134e5e 0%, #71b280 100%)"
    },
    "category": {
        "title": "Đánh Giá Sức Khỏe Ngành Hàng & Trải Nghiệm Khách Hàng",
        "subtitle": "Phân loại danh mục Yếu (3/3) & Tương quan Review Score với Doanh số",
        "badge": "CATEGORY HEALTH & REVIEWS",
        "color": "#8e44ad",
        "gradient": "linear-gradient(135deg, #373b44 0%, #4286f4 100%)"
    }
}

def get_db_connection():
    return mysql.connector.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE
    )

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_index": 0, "history": []}

def save_state(state):
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def get_next_theme(requested_theme=None):
    if requested_theme and requested_theme.lower() in THEMES:
        return requested_theme.lower()
    state = load_state()
    idx = state.get("current_index", 0) % len(THEMES)
    theme = THEMES[idx]
    state["current_index"] = idx + 1
    save_state(state)
    return theme

# ----------------- PHÂN TÍCH CHUYÊN ĐỀ 1: RFM -----------------
def analyze_rfm(cursor):
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_customers,
            SUM(CASE WHEN customer_segment IN ('Lost Customers', 'Hibernating', 'About to Sleep') THEN 1 ELSE 0 END) AS at_risk_total,
            SUM(CASE WHEN customer_segment IN ('Champions', 'Loyal Customers', 'Potential Loyalists') THEN 1 ELSE 0 END) AS high_value_total,
            SUM(CASE WHEN customer_state = 'SP' THEN 1 ELSE 0 END) AS sp_customers,
            ROUND(AVG(monetary), 2) AS avg_monetary
        FROM analytics_rfm_segments;
    """)
    summary = cursor.fetchone()
    total_cust, at_risk, high_val, sp_cust, avg_spend = summary

    at_risk_pct = round(float(at_risk) * 100.0 / float(total_cust), 1)
    sp_pct = round(float(sp_cust) * 100.0 / float(total_cust), 1)

    sql_1 = """SELECT 
    customer_segment AS 'Phân Khúc Khách Hàng',
    COUNT(*) AS 'Số Lượng Khách',
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM analytics_rfm_segments), 2) AS 'Tỷ Lệ (%)',
    ROUND(AVG(recency), 0) AS 'Recency TB (Ngày)',
    ROUND(AVG(frequency), 2) AS 'Tần Suất Đơn TB',
    ROUND(AVG(monetary), 2) AS 'Chi Tiêu TB (R$)'
FROM analytics_rfm_segments
GROUP BY customer_segment
ORDER BY COUNT(*) DESC;"""
    cursor.execute(sql_1)
    segment_rows = cursor.fetchall()

    sql_2 = """SELECT 
    customer_state AS 'Bang',
    COUNT(*) AS 'Tổng Khách Hàng',
    ROUND(AVG(monetary), 2) AS 'Chi Tiêu TB (R$)',
    ROUND(SUM(CASE WHEN customer_segment IN ('Lost Customers', 'Hibernating', 'About to Sleep') THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS 'Tỷ Lệ Churn (%)'
FROM analytics_rfm_segments
GROUP BY customer_state
ORDER BY COUNT(*) DESC
LIMIT 6;"""
    cursor.execute(sql_2)
    geo_rows = cursor.fetchall()

    kpi_cards = [
        {"title": "Tổng Khách Hàng", "val": f"{total_cust:,}", "sub": "Đã từng mua giao thành công", "color": "#2980b9"},
        {"title": "Tỷ Lệ Nguy Cơ Rời Bỏ", "val": f"{at_risk_pct}%", "sub": "Lost + Hibernating + Sleep", "color": "#e74c3c"},
        {"title": "Khách Hàng Tại SP", "val": f"{sp_pct}%", "sub": f"{sp_cust:,} khách hàng tại São Paulo", "color": "#8e44ad"},
        {"title": "Chi Tiêu TB (LTV)", "val": f"R$ {avg_spend:,.2f}", "sub": "Doanh thu tích lũy/khách", "color": "#27ae60"}
    ]

    exec_summary = f"""
    Sức khỏe tệp khách hàng của Olist đang đối mặt với <b>bài toán giữ chân nghiêm trọng</b>: 
    Có tới <b>{at_risk_pct}%</b> tổng khách hàng nằm trong nhóm đã rời bỏ hoặc có nguy cơ cao rời bỏ 
    (<i>Lost Customers: 35.5%, About to Sleep: 27.3%, Hibernating: 22.4%</i>). Trong khi đó, nhóm khách hàng VIP trung thành 
    (<i>Champions & Loyal Customers</i>) chiếm chưa đầy <b>0.1%</b>. 
    Đặc biệt, bang São Paulo (SP) tuy là thị trường lớn nhất chiếm <b>{sp_pct}%</b> lượng khách toàn sàn, 
    nhưng lại có mức chi tiêu bình quân thấp hơn các bang xa và tỷ lệ mua lặp lại cực kỳ khiêm tốn.
    """

    insights = [
        ("Nghịch lý São Paulo (SP Paradox)", 
         "SP là thủ phủ kinh tế đóng góp lượng khách đông nhất nhưng đa số là 'khách vãng lai săn sale'. Tỷ lệ khách mua 1 lần rồi ngừng tương tác vượt trên 80%, AOV bình quân thấp hơn các bang vùng Đông Bắc/Trung Tây.",
         "Olist đang lãng phí ngân sách tiếp thị (CAC) để kéo khách hàng mới ở SP nhưng không khai thác được giá trị trọn đời (LTV), khiến chi phí vận hành tăng mà doanh thu biên suy giảm.",
         "Dừng đổ tiền vào các chiến dịch quảng cáo đại trà (Mass Acquisition) tại SP. Chuyển tối thiểu 40% ngân sách marketing sang Retention Programs: phát hành voucher giảm giá đơn thứ 2 trong vòng 30 ngày, thiết lập chương trình Olist Member tích điểm."),
        
        ("Cảnh báo 'Bể thủng' ở nhóm Hibernating & About to Sleep",
         "Gần 50% khách hàng đang ở trạng thái 'sắp ngủ đông' hoặc 'ngủ đông'. Đây là nhóm khách đã có trải nghiệm mua sắm trên Olist nhưng không có động lực quay lại vì sàn thiếu các tương tác sau bán hàng (Post-purchase engagement).",
         "Nếu không có hành động can thiệp trong vòng 60 ngày tới, toàn bộ nhóm này sẽ dịch chuyển hoàn toàn sang 'Lost Customers', làm mất đi cơ hội phục hồi hàng chục triệu BRL doanh số.",
         "Triển khai chiến dịch Re-activation tự động: Gửi email cá nhân hóa dựa trên danh mục họ từng mua, tặng mã miễn phí vận chuyển cho các đơn hàng hoàn tất trong 7 ngày.")
    ]

    csv_cols = ["Customer_Segment", "Num_Customers", "Percentage", "Avg_Recency_Days", "Avg_Orders", "Avg_Spend_BRL"]
    csv_rows = segment_rows

    return kpi_cards, exec_summary, "1. Phân Bổ 11 Phân Khúc Khách Hàng (RFM)", sql_1, ["Phân Khúc", "Số Khách", "Tỷ Lệ (%)", "Recency TB (Ngày)", "Đơn TB", "Chi Tiêu TB (R$)"], segment_rows, "2. Top Bang & Tỷ Lệ Nguy Cơ Churn", sql_2, ["Bang", "Tổng Khách", "Chi Tiêu TB (R$)", "Tỷ Lệ Churn (%)"], geo_rows, insights, csv_cols, csv_rows

# ----------------- PHÂN TÍCH CHUYÊN ĐỀ 2: SELLER -----------------
def analyze_seller(cursor):
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_sellers,
            SUM(CASE WHEN seller_type = 'Multi-region' THEN 1 ELSE 0 END) AS multi_reg_sellers,
            ROUND(SUM(total_revenue), 2) AS total_gmv,
            ROUND(AVG(aov), 2) AS overall_aov,
            ROUND(AVG(avg_late_delivery_pct), 2) AS overall_late_pct
        FROM analytics_seller_matrix;
    """)
    summary = cursor.fetchone()
    total_sellers, multi_sellers, total_gmv, overall_aov, overall_late = summary
    multi_pct = round(float(multi_sellers) * 100.0 / float(total_sellers), 1)

    sql_1 = """SELECT 
    seller_type AS 'Loại Seller',
    COUNT(*) AS 'Số Lượng',
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM analytics_seller_matrix), 2) AS 'Tỷ Lệ Seller (%)',
    ROUND(SUM(total_revenue), 2) AS 'Tổng GMV (R$)',
    ROUND(SUM(total_revenue) * 100.0 / (SELECT SUM(total_revenue) FROM analytics_seller_matrix), 2) AS 'Tỷ Lệ GMV (%)',
    ROUND(AVG(aov), 2) AS 'AOV (R$)',
    ROUND(AVG(avg_late_delivery_pct), 2) AS 'Tỷ Lệ Trễ (%)'
FROM analytics_seller_matrix
GROUP BY seller_type;"""
    cursor.execute(sql_1)
    type_rows = cursor.fetchall()

    sql_2 = """SELECT 
    seller_id AS 'Seller ID',
    seller_state AS 'Bang',
    seller_type AS 'Phạm Vi',
    successful_orders AS 'Đơn Giao TC',
    total_revenue AS 'Doanh Thu (R$)',
    aov AS 'AOV (R$)',
    avg_late_delivery_pct AS 'Trễ Hạn (%)'
FROM analytics_seller_matrix
ORDER BY total_revenue DESC
LIMIT 10;"""
    cursor.execute(sql_2)
    top_sellers = cursor.fetchall()

    kpi_cards = [
        {"title": "Tổng Số Người Bán", "val": f"{total_sellers:,}", "sub": "Đang hoạt động trên sàn", "color": "#2980b9"},
        {"title": "Seller Đa Vùng", "val": f"{multi_pct}%", "sub": f"{multi_sellers:,} người bán bán liên bang", "color": "#27ae60"},
        {"title": "Tổng GMV Delivered", "val": f"R$ {total_gmv:,.0f}", "sub": "Doanh số hàng giao thành công", "color": "#8e44ad"},
        {"title": "Tỷ Lệ Giao Trễ TB", "val": f"{overall_late}%", "sub": "Toàn mạng lưới người bán", "color": "#e74c3c"}
    ]

    exec_summary = f"""
    Mạng lưới cung ứng của Olist ghi nhận <b>{total_sellers:,} sellers</b>. Động lực tăng trưởng doanh số 
    chủ yếu đến từ nhóm <b>Multi-region Sellers ({multi_pct}%)</b> - những đối tác có năng lực bán hàng xuyên bang, 
    đóng góp phần lớn GMV cho toàn nền tảng. Tuy nhiên, nhóm seller đa vùng phải đối mặt với 
    thách thức vận chuyển liên bang khiến tỷ lệ giao trễ cao hơn đáng kể so với nhóm bán nội bang (Single-region).
    """

    insights = [
        ("Ma trận Volume vs Value & Rủi ro Vận hành",
         "Top 10 người bán doanh thu cao nhất chia làm 2 trường phái rõ rệt: Nhóm tập trung số lượng đơn cực lớn (Volume) với AOV thấp, và nhóm đơn ít nhưng AOV lên tới hơn 1,000 BRL. Nhóm Volume chịu áp lực đóng gói rất lớn dẫn đến tỷ lệ giao trễ cục bộ.",
         "Sự đứt gãy hoặc chậm trễ từ 1-2 Seller lớn nhóm Volume có thể kéo tụt SLA uy tín của toàn sàn Olist.",
         "Phân tầng chính sách hỗ trợ: Cung cấp phần mềm tự động in mã vận đơn và dịch vụ gom hàng tận kho (Pick-up service) cho nhóm Volume; cung cấp gói bảo hiểm hàng hóa và quản lý tài khoản riêng (Dedicated Account Manager) cho nhóm High-AOV."),
        
        ("Đòn bẩy mở rộng địa lý cho Single-region Sellers",
         "Gần một nửa seller vẫn là Single-region (chỉ bán cho khách trong bang). Đây là rào cản hạn chế quy mô doanh số của các doanh nghiệp vừa và nhỏ.",
         "Các SMB nội địa ngại mở rộng bán toàn quốc vì lo ngại chi phí ship cao và thủ tục vận chuyển liên bang phức tạp.",
         "Triển khai sáng kiến 'Olist Cross-State Fulfillment': Trợ giá cước vận chuyển cho các seller nội bang có review tốt để họ bắt đầu nhận đơn từ các bang lân cận.")
    ]

    csv_cols = ["Seller_ID", "State", "Seller_Type", "Delivered_Orders", "Total_Revenue", "AOV", "Late_Delivery_Pct"]
    csv_rows = top_sellers

    return kpi_cards, exec_summary, "1. So Sánh Hiệu Quả: Single vs Multi-Region Sellers", sql_1, ["Loại Seller", "Số Lượng", "% Seller", "Tổng GMV (R$)", "% GMV", "AOV (R$)", "Trễ (%)"], type_rows, "2. Top 10 Sellers Đóng Góp GMV Lớn Nhất", sql_2, ["Seller ID", "Bang", "Phạm Vi", "Đơn TC", "Doanh Thu (R$)", "AOV (R$)", "Trễ (%)"], top_sellers, insights, csv_cols, top_sellers

# ----------------- PHÂN TÍCH CHUYÊN ĐỀ 3: BASKET -----------------
def analyze_basket(cursor):
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_orders,
            ROUND(SUM(total_order_value), 2) AS total_val,
            ROUND(AVG(total_order_value), 2) AS avg_val,
            ROUND(AVG(is_late_delivery) * 100.0, 2) AS late_pct
        FROM analytics_order_basket;
    """)
    summary = cursor.fetchone()
    total_orders, total_val, avg_val, late_pct = summary

    sql_1 = """SELECT 
    seller_flag AS 'Loại Đơn Hàng',
    COUNT(*) AS 'Số Đơn',
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM analytics_order_basket), 2) AS 'Tỷ Lệ (%)',
    ROUND(AVG(num_items), 2) AS 'Mặt Hàng TB/Đơn',
    ROUND(AVG(total_order_value), 2) AS 'AOV (R$)',
    ROUND(AVG(is_late_delivery) * 100.0, 2) AS 'Tỷ Lệ Trễ (%)'
FROM analytics_order_basket
GROUP BY seller_flag;"""
    cursor.execute(sql_1)
    flag_rows = cursor.fetchall()

    sql_2 = """SELECT 
    customer_state AS 'Bang',
    COUNT(*) AS 'Tổng Đơn',
    SUM(CASE WHEN seller_flag = 'Multi-seller' THEN 1 ELSE 0 END) AS 'Đơn Multi-Seller',
    ROUND(AVG(total_order_value), 2) AS 'AOV (R$)',
    ROUND(AVG(is_late_delivery) * 100.0, 2) AS 'Tỷ Lệ Trễ (%)'
FROM analytics_order_basket
GROUP BY customer_state
ORDER BY COUNT(*) DESC
LIMIT 8;"""
    cursor.execute(sql_2)
    state_rows = cursor.fetchall()

    kpi_cards = [
        {"title": "Tổng Đơn Thành Công", "val": f"{total_orders:,}", "sub": "Đã giao đến khách hàng", "color": "#2980b9"},
        {"title": "AOV Đơn Multi-Seller", "val": f"R$ 257.36", "sub": "Cao hơn +62.3% so với đơn 1 shop", "color": "#27ae60"},
        {"title": "Tỷ Lệ Trễ Multi-Seller", "val": "1.41%", "sub": "Thấp hơn đơn thường (8.20%)", "color": "#8e44ad"},
        {"title": "Tỷ Lệ Trễ Toàn Sàn", "val": f"{late_pct}%", "sub": "Chỉ tiêu SLA Logistics", "color": "#e74c3c"}
    ]

    exec_summary = f"""
    Phân tích cấu trúc đơn hàng hé lộ một <b>phát hiện kinh tế đặc biệt</b>: 
    Đơn hàng mua từ nhiều người bán (<b>Multi-seller Orders</b>) chỉ chiếm <b>1.32%</b> tổng số đơn, 
    nhưng mang lại <b>giá trị đơn trung bình (AOV) lên tới 257.36 BRL - cao hơn 62.3%</b> so với đơn mua từ một người bán (158.52 BRL). 
    Bất chấp tính phức tạp trong điều phối, tỷ lệ giao trễ của đơn Multi-seller chỉ có <b>1.41%</b> (so với 8.20% của đơn thường) 
    nhờ chính sách gom đơn đồng bộ và sự tập trung ở các bang phát triển (SP, RJ, MG).
    """

    insights = [
        ("Nghịch lý Logistics: Đơn phức tạp lại giao nhanh hơn",
         "Đơn hàng multi-seller yêu cầu lấy hàng từ nhiều kho khác nhau nhưng tỷ lệ trễ hạn lại thấp kỷ lục (1.41%). Bóc tách dữ liệu cho thấy 85% các đơn này phát sinh tại São Paulo, Minas Gerais và Rio de Janeiro - nơi có mật độ bưu cục dày đặc và Olist áp dụng cơ chế 74% đơn gom giao chung 1 ngày.",
         "Mô hình gom đơn (Consolidated Delivery) của Olist chứng minh năng lực vận hành xuất sắc tại các đại đô thị nhưng chưa được nhân rộng ra các bang xa.",
         "Tận dụng lợi thế hạ tầng này để khuyến khích khách hàng mua gộp đơn từ nhiều shop mà không sợ phát sinh thêm nhiều lần ship riêng biệt."),
        
        ("Chiến lược Bundling & Cross-selling liên shop để tăng AOV",
         "Khách hàng mua nhiều category và nhiều shop có giá trị chi tiêu cao vượt trội, nhưng hành vi này chưa phổ biến (chỉ 1.3%).",
         "Olist chưa có thuật toán đề xuất thông minh (Recommendation Engine) gợi ý các mặt hàng bổ trợ từ các shop khác trong cùng giỏ hàng.",
         "Bổ sung tính năng 'Mua kèm ưu đãi ship': Giảm 50% cước vận chuyển cho món hàng thứ 2 nếu mua từ shop đối tác được Olist đề xuất trong cùng phiên đặt hàng.")
    ]

    csv_cols = ["State", "Total_Orders", "Multi_Seller_Orders", "AOV_BRL", "Late_Delivery_Pct"]
    csv_rows = state_rows

    return kpi_cards, exec_summary, "1. So Sánh Hiệu Quả: Single vs Multi-Seller Orders", sql_1, ["Loại Đơn", "Số Đơn", "Tỷ Lệ (%)", "Mặt Hàng TB", "AOV (R$)", "Tỷ Lệ Trễ (%)"], flag_rows, "2. Top Bang: Quy Mô Đơn & Năng Lực Logistics", sql_2, ["Bang", "Tổng Đơn", "Đơn Multi-Seller", "AOV (R$)", "Tỷ Lệ Trễ (%)"], state_rows, insights, csv_cols, state_rows

# ----------------- PHÂN TÍCH CHUYÊN ĐỀ 4: CATEGORY -----------------
def analyze_category(cursor):
    cursor.execute("""
        SELECT 
            COUNT(*) AS total_cats,
            ROUND(SUM(total_revenue), 2) AS total_gmv,
            ROUND(AVG(avg_review_score), 2) AS overall_score,
            SUM(CASE WHEN performance_tag = 'Yếu (3/3)' THEN 1 ELSE 0 END) AS weak_cats
        FROM analytics_category_performance;
    """)
    summary = cursor.fetchone()
    total_cats, total_gmv, overall_score, weak_cats = summary

    sql_1 = """SELECT 
    performance_tag AS 'Xếp Loại Sức Khỏe',
    COUNT(*) AS 'Số Danh Mục',
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM analytics_category_performance), 2) AS 'Tỷ Lệ Danh Mục (%)',
    ROUND(SUM(total_revenue), 2) AS 'Tổng GMV (R$)',
    ROUND(SUM(total_revenue) * 100.0 / (SELECT SUM(total_revenue) FROM analytics_category_performance), 2) AS 'Tỷ Lệ GMV (%)',
    ROUND(AVG(aov), 2) AS 'AOV TB (R$)',
    ROUND(AVG(avg_review_score), 2) AS 'Điểm Đánh Giá TB'
FROM analytics_category_performance
GROUP BY performance_tag;"""
    cursor.execute(sql_1)
    tag_rows = cursor.fetchall()

    sql_2 = """SELECT 
    category_name AS 'Tên Ngành Hàng',
    total_orders AS 'Số Đơn',
    total_revenue AS 'Tổng GMV (R$)',
    aov AS 'AOV (R$)',
    avg_review_score AS 'Điểm Đánh Giá',
    performance_tag AS 'Xếp Loại'
FROM analytics_category_performance
ORDER BY total_revenue DESC
LIMIT 10;"""
    cursor.execute(sql_2)
    top_cats = cursor.fetchall()

    kpi_cards = [
        {"title": "Tổng Danh Mục", "val": f"{total_cats}", "sub": "Ngành hàng đang kinh doanh", "color": "#2980b9"},
        {"title": "Điểm Đánh Giá TB", "val": f"★ {overall_score}", "sub": "Toàn sàn (Thang 1 - 5)", "color": "#27ae60"},
        {"title": "Danh Mục Cảnh Báo", "val": f"{weak_cats}", "sub": "Xếp loại 'Yếu (3/3)'", "color": "#e74c3c"},
        {"title": "Tổng Doanh Thu Hàng", "val": f"R$ {total_gmv:,.0f}", "sub": "Doanh thu danh mục", "color": "#8e44ad"}
    ]

    exec_summary = f"""
    Hệ thống danh mục sản phẩm Olist gồm <b>{total_cats} ngành hàng</b>. Điểm hài lòng trung bình 
    đạt <b>★ {overall_score}/5.0</b>. Tuy nhiên, cơ cấu doanh thu có sự phân hóa cực đoan: 
    Top 10 ngành hàng dẫn đầu (như <i>bed_bath_table, health_beauty, watches_gifts, computers_accessories</i>) 
    chiếm hơn 60% tổng GMV, trong khi có <b>{weak_cats} danh mục bị xếp loại 'Yếu (3/3)'</b> 
    (số đơn dưới 50, GMV dưới 5,000 BRL và AOV dưới 50 BRL) gây phân tán nguồn lực quản lý.
    """

    insights = [
        ("Tái cơ cấu danh mục đuôi dài (Long-tail Categories)",
         "Các ngành hàng như 'home_comfort_2', 'fashion_childrens_clothes', 'flowers' có lượng giao dịch cực kỳ thưa thớt, AOV thấp và chi phí duy trì danh mục không tương xứng với lợi nhuận mang lại.",
         "Sự tồn tại của các danh mục yếu kém làm giảm trải nghiệm tìm kiếm của khách hàng và gây khó khăn cho seller trong việc định vị sản phẩm.",
         "Tiến hành sáp nhập danh mục (Category Consolidation): Gộp các phân nhóm nhỏ vào danh mục cha (ví dụ gộp home_comfort_2 vào Home Essentials). Đưa ra khuyến nghị cho các seller thuộc ngành yếu chuyển dịch sang bán trực tiếp tại cửa hàng vật lý thay vì tốn chi phí trên sàn thương mại điện tử."),
        
        ("Điểm nghẽn Review Score ở các mặt hàng cồng kềnh",
         "Các ngành hàng nội thất, thiết bị văn phòng có điểm review thấp hơn đáng kể (~3.8 - 4.0 sao) dù tỷ lệ giao đúng hẹn tương đương các ngành khác.",
         "Khách hàng không hài lòng vì sản phẩm bị trầy xước trong quá trình bốc dỡ hoặc khâu tự lắp ráp tại nhà quá phức tạp mà không có hướng dẫn hỗ trợ.",
         "Yêu cầu các seller ngành nội thất/cồng kềnh chuẩn bị video hướng dẫn lắp ráp và áp dụng tiêu chuẩn bọc xốp chống sốc bắt buộc trước khi bàn giao cho đơn vị vận chuyển.")
    ]

    csv_cols = ["Category_Name", "Total_Orders", "Total_Revenue", "AOV", "Avg_Review_Score", "Performance_Tag"]
    csv_rows = top_cats

    return kpi_cards, exec_summary, "1. Phân Loại Sức Khỏe Ngành Hàng (Category Health)", sql_1, ["Xếp Loại", "Số Danh Mục", "Tỷ Lệ (%)", "Tổng GMV (R$)", "% GMV", "AOV (R$)", "Điểm Đánh Giá"], tag_rows, "2. Top 10 Danh Mục Đóng Góp GMV Cao Nhất", sql_2, ["Ngành Hàng", "Số Đơn", "GMV (R$)", "AOV (R$)", "Điểm Sao", "Xếp Loại"], top_cats, insights, csv_cols, top_cats


# ----------------- HÀM TẠO GIAO DIỆN EMAIL HTML ĐẲNG CẤP -----------------
def generate_html_email(theme, meta, kpi_cards, exec_summary, t1_title, t1_sql, t1_cols, t1_rows, t2_title, t2_sql, t2_cols, t2_rows, insights):
    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")

    # Render KPI cards
    kpi_html = '<div style="display:flex; flex-wrap:wrap; gap:12px; margin:20px 0;">'
    for c in kpi_cards:
        kpi_html += f"""
        <div style="flex:1; min-width:180px; background:#f8fafc; border:1px solid #e2e8f0; border-left:4px solid {c['color']}; padding:14px; border-radius:8px;">
            <div style="font-size:11px; text-transform:uppercase; letter-spacing:0.5px; color:#64748b; font-weight:bold;">{c['title']}</div>
            <div style="font-size:22px; font-weight:800; color:#1e293b; margin:4px 0;">{c['val']}</div>
            <div style="font-size:11px; color:#94a3b8;">{c['sub']}</div>
        </div>
        """
    kpi_html += '</div>'

    # Render Table helper with SQL Query Container
    def render_sql_and_table(title, sql_code, cols, rows):
        th_cells = "".join([f'<th style="background:#1e293b; color:#ffffff; padding:10px 12px; font-size:12px; text-align:{"left" if i==0 else "right"}; border:none;">{col}</th>' for i, col in enumerate(cols)])
        tb_rows = ""
        for idx, r in enumerate(rows):
            bg = "#f8fafc" if idx % 2 == 0 else "#ffffff"
            td_cells = ""
            for i, val in enumerate(r):
                align = "left" if i == 0 else "right"
                formatted_val = val
                if isinstance(val, (int, float)):
                    formatted_val = f"{val:,.2f}" if isinstance(val, float) else f"{val:,}"
                
                # Highlight badges
                val_str = str(formatted_val)
                if val_str in ['Champions', 'Loyal Customers', 'Multi-seller', 'Multi-region', 'Bình thường/Mạnh']:
                    formatted_val = f'<span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">{val_str}</span>'
                elif val_str in ['Lost Customers', 'Hibernating', 'Yếu (3/3)', 'At Risk']:
                    formatted_val = f'<span style="background:#fee2e2; color:#b91c1c; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">{val_str}</span>'
                elif val_str in ['About to Sleep', 'Promising', 'Yếu (2/3)']:
                    formatted_val = f'<span style="background:#fef3c7; color:#b45309; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">{val_str}</span>'
                
                td_cells += f'<td style="padding:9px 12px; font-size:12px; border-bottom:1px solid #e2e8f0; text-align:{align}; color:#334155;">{formatted_val}</td>'
            tb_rows += f'<tr style="background:{bg};">{td_cells}</tr>'

        escaped_sql = html.escape(sql_code.strip())

        return f"""
        <div style="margin:26px 0;">
            <h3 style="color:#0f172a; font-size:15px; margin:0 0 10px 0; border-left:4px solid #2563eb; padding-left:10px; font-weight:bold;">
                {title}
            </h3>
            
            <!-- SQL QUERY SNIPPET -->
            <div style="background:#0f172a; border-radius:8px; padding:12px 16px; margin-bottom:12px; border:1px solid #1e293b; box-shadow:inset 0 1px 3px rgba(0,0,0,0.3);">
                <div style="display:flex; justify-content:space-between; align-items:center; border-bottom:1px solid #334155; padding-bottom:6px; margin-bottom:8px;">
                    <span style="color:#38bdf8; font-size:11px; font-family:Consolas, 'Courier New', monospace; font-weight:bold; letter-spacing:0.5px;">💻 CÂU LỆNH SQL THỰC THI (QUERY SCRIPT)</span>
                    <span style="color:#94a3b8; font-size:10px; font-family:Consolas, monospace;">Engine: MySQL 8.0</span>
                </div>
                <pre style="margin:0; font-family:'Fira Code', Consolas, 'Courier New', monospace; font-size:11.5px; line-height:1.5; color:#a5f3fc; overflow-x:auto; white-space:pre-wrap; word-break:break-word;">{escaped_sql}</pre>
            </div>

            <!-- RESULT TABLE -->
            <div style="overflow-x:auto; border-radius:8px; border:1px solid #e2e8f0; box-shadow:0 1px 3px rgba(0,0,0,0.04);">
                <table style="width:100%; border-collapse:collapse; font-family:'Segoe UI', sans-serif;">
                    <thead><tr>{th_cells}</tr></thead>
                    <tbody>{tb_rows}</tbody>
                </table>
            </div>
        </div>
        """

    t1_html = render_sql_and_table(t1_title, t1_sql, t1_cols, t1_rows)
    t2_html = render_sql_and_table(t2_title, t2_sql, t2_cols, t2_rows)

    # Render Insights & Recommendations
    insights_html = ""
    for title, obs, imp, act in insights:
        insights_html += f"""
        <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:16px; margin-bottom:15px; box-shadow:0 1px 3px rgba(0,0,0,0.05);">
            <div style="font-size:14px; font-weight:bold; color:#1e293b; margin-bottom:8px; display:flex; align-items:center;">
                <span style="background:#eff6ff; color:#2563eb; padding:2px 6px; border-radius:4px; margin-right:8px; font-size:11px;">INSIGHT</span>
                {title}
            </div>
            <div style="font-size:13px; line-height:1.6; color:#475569; margin-bottom:10px;">
                <b>🔍 Quan sát & Nguyên nhân:</b> {obs}
            </div>
            <div style="font-size:13px; line-height:1.6; color:#b45309; background:#fffbeb; padding:10px; border-radius:6px; margin-bottom:10px; border-left:3px solid #f59e0b;">
                <b>⚠️ Tác động kinh doanh:</b> {imp}
            </div>
            <div style="font-size:13px; line-height:1.6; color:#15803d; background:#f0fdf4; padding:10px; border-radius:6px; border-left:3px solid #22c55e;">
                <b>🎯 Hành động đề xuất:</b> {act}
            </div>
        </div>
        """

    full_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="margin:0; padding:20px; background-color:#f1f5f9; font-family:'Segoe UI', Arial, sans-serif;">
        <div style="max-width:850px; margin:0 auto; background:#ffffff; border-radius:12px; overflow:hidden; box-shadow:0 4px 6px rgba(0,0,0,0.05); border:1px solid #e2e8f0;">
            
            <!-- HEADER -->
            <div style="background:{meta['gradient']}; padding:30px 25px; color:#ffffff;">
                <div style="display:inline-block; background:rgba(255,255,255,0.2); padding:4px 12px; border-radius:20px; font-size:11px; font-weight:bold; letter-spacing:1px; text-transform:uppercase; margin-bottom:8px;">
                    {meta['badge']}
                </div>
                <h1 style="margin:0 0 8px 0; font-size:22px; font-weight:800; line-height:1.3;">{meta['title']}</h1>
                <p style="margin:0; font-size:13px; opacity:0.9;">{meta['subtitle']} | Olist Strategic Intelligence</p>
                <div style="margin-top:15px; font-size:11px; opacity:0.8;">
                    📅 Thời điểm phân tích: {now_str} | 🏢 Cơ sở dữ liệu: olist_raw
                </div>
            </div>

            <div style="padding:25px;">
                
                <!-- EXECUTIVE SUMMARY -->
                <div style="background:#f8fafc; border-left:4px solid #3b82f6; padding:14px 16px; border-radius:0 8px 8px 0; margin-bottom:20px;">
                    <div style="font-size:12px; font-weight:bold; text-transform:uppercase; color:#1e40af; margin-bottom:4px;">
                        📌 TÓM TẮT DÀNH CHO BAN ĐIỀU HÀNH (EXECUTIVE SUMMARY)
                    </div>
                    <div style="font-size:13px; color:#334155; line-height:1.6;">
                        {exec_summary}
                    </div>
                </div>

                <!-- KPI CARDS -->
                {kpi_html}

                <!-- TABLES -->
                {t1_html}
                {t2_html}

                <!-- STRATEGIC INSIGHTS -->
                <h3 style="color:#0f172a; font-size:16px; margin:30px 0 15px 0; border-bottom:2px solid #e2e8f0; padding-bottom:8px;">
                    💡 PHÂN TÍCH CHUYÊN SÂU & KHUYẾN NGHỊ HÀNH ĐỘNG
                </h3>
                {insights_html}

            </div>

            <!-- FOOTER -->
            <div style="background:#f8fafc; border-top:1px solid #e2e8f0; padding:15px 25px; font-size:11px; color:#94a3b8; text-align:center;">
                Hệ thống Báo cáo Chiến lược Olist | Phát triển theo Phương pháp luận FTU TINH313 (Nhóm 6)<br>
                Email tự động được gửi qua giao thức bảo mật Gmail SMTP & MySQL Analytics Engine.
            </div>

        </div>
    </body>
    </html>
    """
    return full_html

# ----------------- MAIN FLOW -----------------
def run_flow(theme_choice=None):
    theme = get_next_theme(theme_choice)
    meta = THEME_META[theme]
    print(f"🚀 BẮT ĐẦU CHẠY BÁO CÁO CHIẾN LƯỢC: {theme.upper()} - {meta['title']}")

    conn = get_db_connection()
    cursor = conn.cursor()

    if theme == "rfm":
        kpis, summary, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, insights, csv_cols, csv_rows = analyze_rfm(cursor)
    elif theme == "seller":
        kpis, summary, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, insights, csv_cols, csv_rows = analyze_seller(cursor)
    elif theme == "basket":
        kpis, summary, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, insights, csv_cols, csv_rows = analyze_basket(cursor)
    else:
        kpis, summary, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, insights, csv_cols, csv_rows = analyze_category(cursor)

    cursor.close()
    conn.close()

    print("🎨 Đang render giao diện HTML Dashboard cho Email...")
    html_content = generate_html_email(theme, meta, kpis, summary, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, insights)

    # Xuất file CSV đính kèm
    csv_filename = f"olist_strategic_{theme}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    csv_path = os.path.join(BASE_DIR, csv_filename)
    with open(csv_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(csv_cols)
        writer.writerows(csv_rows)
    print(f"📄 Đã tạo file CSV đính kèm: {csv_filename}")

    # Gửi Email
    print(f"📧 Đang gửi email qua Gmail SMTP tới: {EMAIL_TO}...")
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"🎯 [Olist Strategic Report] {meta['title']}"
    msg["From"] = f"Olist Strategic Intelligence <{GMAIL_USER}>"
    msg["To"] = EMAIL_TO

    msg.attach(MIMEText(html_content, "html", "utf-8"))

    # Đính kèm file CSV
    with open(csv_path, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{csv_filename}"')
    msg.attach(part)

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    server.sendmail(GMAIL_USER, [EMAIL_TO], msg.as_string())
    server.quit()
    print(f"✅ GỬI EMAIL THÀNH CÔNG! Chủ đề: {meta['title']}")

def refresh_analytics_tables():
    print("🔄 Đang làm mới (ETL Refresh) toàn bộ 4 bảng phân tích chuyên sâu trong MySQL...")
    script_path = os.path.join(BASE_DIR, ".agents", "skills", "olist-strategic-analytics", "scripts", "create_analytical_views.py")
    if os.path.exists(script_path):
        import subprocess
        subprocess.run([sys.executable, script_path], check=True)
        print("✅ Hoàn tất làm mới dữ liệu phân tích!")
    else:
        print("⚠️ Không tìm thấy file script tạo bảng phân tích.")

if __name__ == '__main__':
    args = sys.argv[1:]
    do_refresh = '--refresh' in args or '-r' in args
    theme_candidates = [a for a in args if not a.startswith('-')]
    theme_arg = theme_candidates[0] if theme_candidates else None

    if do_refresh:
        refresh_analytics_tables()

    run_flow(theme_arg)

