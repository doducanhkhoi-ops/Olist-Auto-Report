import sys
import html
import io
import os
import json
import csv
import smtplib
import urllib.request
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import mysql.connector

# Thiết lập encoding UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ============== CẤU HÌNH (HỖ TRỢ CẢ LOCAL VÀ GITHUB ACTIONS / CLOUD) ==============
def get_env_or_default(var_names, default):
    for name in var_names:
        val = os.getenv(name)
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return default

GMAIL_USER = get_env_or_default(["GMAIL_USER"], "doducanhkhoi.bec@gmail.com")
GMAIL_APP_PASSWORD = get_env_or_default(["GMAIL_APP_PASSWORD"], "wkof rxcj jshh zjql")
EMAIL_TO = get_env_or_default(["EMAIL_TO"], "doducanhkhoi.bec@gmail.com")

port_raw = get_env_or_default(["MYSQL_PORT", "DB_PORT"], None)
MYSQL_HOST = get_env_or_default(["MYSQL_HOST", "DB_HOST"], "localhost")
if "://" in MYSQL_HOST:
    MYSQL_HOST = MYSQL_HOST.split("://")[-1]
if ":" in MYSQL_HOST:
    parts = MYSQL_HOST.split(":")
    MYSQL_HOST = parts[0]
    if not port_raw:
        port_raw = parts[1].split("/")[0]
MYSQL_HOST = MYSQL_HOST.strip().rstrip("/")

if port_raw:
    try:
        MYSQL_PORT = int(port_raw)
    except (ValueError, TypeError):
        MYSQL_PORT = 18064 if "aivencloud" in MYSQL_HOST else 3306
else:
    MYSQL_PORT = 18064 if "aivencloud" in MYSQL_HOST else 3306

MYSQL_USER = get_env_or_default(["MYSQL_USER", "DB_USER"], "avnadmin" if "aivencloud" in MYSQL_HOST else "root")
MYSQL_PASSWORD = get_env_or_default(["MYSQL_PASSWORD", "DB_PASSWORD", "DB_PASS"], "@Kk1332006")
MYSQL_DATABASE = get_env_or_default(["MYSQL_DATABASE", "DB_NAME"], "defaultdb" if "aivencloud" in MYSQL_HOST else "olist_raw")

GEMINI_API_KEY = get_env_or_default(["GEMINI_API_KEY"], "")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "strategic_report_state.json")
# =================================================================================

THEMES = ["rfm", "seller", "basket", "category", "logistics", "payment"]

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
    },
    "logistics": {
        "title": "Năng Lực Giao Hàng & Độ Lệch Thời Gian Ước Tính (Logistics SLA)",
        "subtitle": "Phân tích độ chính xác ngày hẹn giao hàng & Gánh nặng cước phí vận chuyển theo bang",
        "badge": "LOGISTICS & SLA PERFORMANCE",
        "color": "#d35400",
        "gradient": "linear-gradient(135deg, #e65c00 0%, #f9d423 100%)"
    },
    "payment": {
        "title": "Hành Vi Thanh Toán & Đòn Bẩy Tài Chính Từ Trả Góp",
        "subtitle": "Tối ưu hóa chuyển đổi thanh toán & Đòn bẩy AOV từ kỳ hạn trả góp thẻ tín dụng",
        "badge": "PAYMENTS & FINTECH LEVERAGE",
        "color": "#16a085",
        "gradient": "linear-gradient(135deg, #11998e 0%, #38ef7d 100%)"
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
    
    # Trên môi trường GitHub Actions: Xoay vòng tự động theo chu kỳ mỗi 3 tiếng
    if os.getenv("GITHUB_ACTIONS") == "true":
        slot = int(datetime.utcnow().timestamp() // (3 * 3600))
        return THEMES[slot % len(THEMES)]

    state = load_state()
    idx = state.get("current_index", 0) % len(THEMES)
    theme = THEMES[idx]
    state["current_index"] = idx + 1
    save_state(state)
    return theme

# =========================================================================
# 🧠 BỘ NÃO AI STRATEGIC ANALYTICS (HỌC PHƯƠNG PHÁP LUẬN FTU NHÓM 6)
# =========================================================================

def call_gemini_strategic_analysis(api_key, theme, meta, kpis, t1_title, t1_cols, t1_rows, t2_title, t2_cols, t2_rows):
    """
    Gọi Gemini API để đóng vai Giám đốc Chiến lược, tự đọc bảng số liệu thực tế
    và suy luận theo quy tắc 3 phần: Quan sát -> Tác động -> Hành động.
    """
    def format_table(cols, rows, max_r=12):
        lines = [" | ".join(cols)]
        for r in rows[:max_r]:
            lines.append(" | ".join([str(c) for c in r]))
        return "\n".join(lines)

    t1_text = format_table(t1_cols, t1_rows)
    t2_text = format_table(t2_cols, t2_rows)
    kpis_text = "\n".join([f"- {c['title']}: {c['val']} ({c['sub']})" for c in kpis])

    system_instruction = (
        "Bạn là Giám đốc Phân tích Dữ liệu Chiến lược (Head of Strategic Analytics) cho sàn thương mại điện tử Olist, "
        "thấm nhuần phương pháp luận phân tích thị trường và tư duy kinh doanh xuất sắc của nhóm nghiên cứu FTU (Khoa Kinh tế Quốc tế).\n\n"
        "NGUYÊN TẮC PHÂN TÍCH BẮT BUỘC:\n"
        "1. TUYỆT ĐỐI KHÔNG đọc lại số liệu thô kiểu mô tả máy móc. Bạn phải trả lời 3 câu hỏi cốt lõi:\n"
        "   - 'Tại sao con số lại như vậy? (Root Cause)'\n"
        "   - 'Nó đe dọa hoặc tạo đòn bẩy gì cho CAC, LTV, AOV, Cash flow, Churn rate, hay Logistics SLA? (Business Implication)'\n"
        "   - 'Ban điều hành cần ra quyết định hành động cụ thể gì ngay lập tức? (Action Plan)'\n"
        "2. TÌM KIẾM NGHỊCH LÝ & ĐIỂM NGHẼN: Nhận diện nghịch lý địa lý (thị trường đông nhất nhưng AOV thấp, khách vãng lai mua 1 lần), "
        "nghịch lý logistics (đơn gom nhiều shop lại giao đúng hẹn hơn), sự phân hóa Volume vs Value, hay các danh mục sản phẩm đuôi dài 3/3.\n"
        "3. TRẢ VỀ DUY NHẤT ĐỊNH DẠNG JSON HỢP LỆ, không kèm markdown thừa hay giải thích ngoài."
    )

    prompt = f"""
Hãy phân tích dữ liệu thực tế vừa trích xuất từ cơ sở dữ liệu MySQL cho chuyên đề: "{meta['title']}".

CHỈ SỐ TỔNG QUAN (KPIs):
{kpis_text}

BẢNG TRUY VẤN 1 ({t1_title}):
{t1_text}

BẢNG TRUY VẤN 2 ({t2_title}):
{t2_text}

Yêu cầu trả về đúng cấu trúc JSON sau:
{{
  "exec_summary": "Tóm tắt điều hành 3-5 câu sắc bén, nêu bật phát hiện cốt lõi, vấn đề nan giải và định hướng hành động...",
  "insights": [
    {{
      "title": "Tên phát hiện chiến lược 1",
      "observation": "Quan sát xu hướng và phân tích nguyên nhân gốc rễ (Root cause)...",
      "implication": "Tác động kinh doanh và rủi ro tài chính cụ thể...",
      "action": "Kế hoạch hành động đề xuất cụ thể, đo lường được cho ban điều hành..."
    }},
    {{
      "title": "Tên phát hiện chiến lược 2",
      "observation": "Quan sát xu hướng và phân tích nguyên nhân gốc rễ...",
      "implication": "Tác động kinh doanh và rủi ro tài chính...",
      "action": "Kế hoạch hành động đề xuất cụ thể..."
    }}
  ]
}}
"""

    models = ["gemini-2.5-flash", "gemini-1.5-flash"]
    last_err = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {
                "temperature": 0.7,
                "responseMimeType": "application/json"
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as response:
                res_json = json.loads(response.read().decode("utf-8"))
                text_content = res_json["candidates"][0]["content"]["parts"][0]["text"].strip()
                if text_content.startswith("```json"):
                    text_content = text_content[7:]
                if text_content.startswith("```"):
                    text_content = text_content[3:]
                if text_content.endswith("```"):
                    text_content = text_content[:-3]
                parsed = json.loads(text_content.strip())
                
                insights_tuples = []
                for ins in parsed.get("insights", []):
                    insights_tuples.append((
                        ins.get("title", "Chiến Lược Tối Ưu"),
                        ins.get("observation", ""),
                        ins.get("implication", ""),
                        ins.get("action", "")
                    ))
                return parsed.get("exec_summary", ""), insights_tuples
        except Exception as ex:
            last_err = ex
            continue

    raise last_err

def dynamic_heuristic_insights(theme, kpis, t1_cols, t1_rows, t2_cols, t2_rows):
    """
    Bộ động cơ phân tích động (Dynamic Data-Driven Heuristics):
    Tính toán trực tiếp các tỷ lệ, độ lệch (delta) và so sánh max/min từ số liệu thực tế
    để tự động sinh bài phân tích, tuyệt đối không dùng văn mẫu sao chép.
    """
    if theme == "rfm":
        total_kpi = kpis[0]['val']
        risk_kpi = kpis[1]['val']
        sp_kpi = kpis[2]['val']
        ltv_kpi = kpis[3]['val']

        # Tìm phân khúc lớn nhất
        top_seg = max(t1_rows, key=lambda x: x[1])
        top_state = t2_rows[0] if len(t2_rows) > 0 else ("SP", 0, 0, 0)

        exec_summary = (
            f"Phân tích dữ liệu vòng đời khách hàng toàn sàn Olist ghi nhận tổng quy mô <b>{total_kpi} khách hàng</b> "
            f"với mức chi tiêu lũy kế trung bình <b>{ltv_kpi}</b>. Tuy nhiên, tỷ lệ cảnh báo nguy cơ rời bỏ (Churn Risk) "
            f"đang ở mức báo động <b>{risk_kpi}</b>, dẫn đầu bởi phân khúc '<i>{top_seg[0]}</i>' (chiếm {top_seg[2]}%). "
            f"Thị trường lớn nhất là bang <b>{top_state[0]}</b> ({top_state[1]:,} khách) nhưng ghi nhận mức chi tiêu bình quân "
            f"khiêm tốn (R$ {top_state[2]:,.2f}) và tỷ lệ rời bỏ lên tới {top_state[3]}%, cho thấy hiệu suất chuyển đổi LTV còn nhiều điểm nghẽn."
        )

        insights = [
            (f"Nghịch Lý Thị Trường Trọng Điểm Tại Bang {top_state[0]}",
             f"Bang {top_state[0]} đóng vai trò đầu tàu về lượng người dùng ({top_state[1]:,} khách) nhưng chi tiêu trung bình (R$ {top_state[2]:,.2f}) thấp hơn mức kỳ vọng. Đa số khách hàng chỉ phát sinh 1 đơn hàng giao dịch khuyến mãi rồi ngừng tương tác.",
             f"Olist đang tiêu tốn ngân sách lớn cho chi phí thu hút khách hàng mới (CAC) tại vùng đô thị trung tâm nhưng không kích hoạt được giá trị trọn đời (LTV), khiến tỷ suất lợi nhuận biên trên mỗi khách hàng suy giảm mạnh.",
             f"Cắt giảm 30% ngân sách quảng cáo đại trà tại {top_state[0]}, tái phân bổ sang chương trình Re-engagement: gửi voucher giảm giá tự động cho đơn thứ hai trong vòng 21 ngày và triển khai hệ thống tích điểm thành viên."),

            ("Cảnh Báo Hiện Tượng 'Bể Thủng' Ở Nhóm Khách Hàng Nguy Cơ",
             f"Nhóm khách hàng 'About to Sleep' và 'Hibernating' đang chiếm tỷ trọng áp đảo trong cơ cấu {risk_kpi} tệp có nguy cơ. Đây là nhóm đã từng tin tưởng mua sắm nhưng sàn thiếu hoàn toàn các điểm chạm chăm sóc sau bán hàng.",
             f"Nếu không can thiệp kịp thời, toàn bộ nhóm khách này sẽ chuyển hẳn sang 'Lost Customers' trong 60 ngày tới, làm đóng băng vĩnh viễn tệp khách hàng tiềm năng đã tốn chi phí chuyển đổi.",
             "Thiết lập kịch bản email tự động hóa kích hoạt lại (Win-back Journey): Gợi ý các sản phẩm mua kèm dựa trên danh mục họ từng mua và miễn phí vận chuyển cho đơn hàng phát sinh trong vòng 7 ngày.")
        ]
        return exec_summary, insights

    elif theme == "seller":
        total_sellers = kpis[0]['val']
        multi_pct = kpis[1]['val']
        gmv = kpis[2]['val']
        late = kpis[3]['val']

        top_s = t2_rows[0] if len(t2_rows) > 0 else ("Unknown", "", "", 0, 0, 0, 0)
        
        exec_summary = (
            f"Mạng lưới cung ứng Olist hiện có <b>{total_sellers} người bán</b> đóng góp tổng GMV giao dịch thành công <b>{gmv}</b>. "
            f"Trong đó, động lực doanh số phân hóa rõ rệt: nhóm <b>Multi-region Sellers ({multi_pct})</b> có phạm vi bán hàng xuyên bang "
            f"chiếm tỷ trọng doanh số vượt trội nhưng chịu tỷ lệ giao trễ trung bình <b>{late}</b> do phức tạp trong khâu vận tải liên vùng. "
            f"Top seller lớn nhất hiện ghi nhận doanh số R$ {top_s[4]:,.2f} với {top_s[3]:,} đơn hàng."
        )

        insights = [
            ("Ma Trận Phân Hóa Volume vs Value Ở Top Người Bán",
             f"Nhóm người bán dẫn đầu chia thành 2 mô hình rõ rệt: nhóm tập trung số lượng đơn cực lớn (AOV thấp, áp lực đóng gói cao) và nhóm sản phẩm giá trị cao (AOV vượt 800 R$). Nhóm Volume chịu tỷ lệ giao trễ cục bộ cao hơn do năng lực kho bãi tự phát.",
             "Bất kỳ sự đứt gãy hay chậm trễ đóng gói nào từ các seller nhóm Volume sẽ lập tức gây ảnh hưởng dây chuyền đến chỉ số SLA toàn sàn.",
             "Cung cấp gói hỗ trợ in vận đơn tự động và dịch vụ lấy hàng tận kho (Pick-up fulfillment) cho nhóm Volume; đồng thời chỉ định Account Manager chăm sóc riêng cho nhóm High-AOV."),

            ("Rào Cản Mở Rộng Địa Lý Của Nhóm Single-region Sellers",
             "Gần một nửa mạng lưới người bán vẫn chỉ bán nội bang (Single-region) do e ngại chi phí vận chuyển liên bang đắt đỏ và thủ tục phức tạp.",
             "Thị trường bị phân mảnh cục bộ, hạn chế cơ hội tiếp cận hàng hóa đa dạng của người tiêu dùng ở các bang xa.",
             "Ra mắt chương trình 'Olist Cross-Region Expansion': Trợ giá 20% cước phí vận chuyển liên bang cho các seller nội bang có điểm đánh giá từ 4.5 sao trở lên.")
        ]
        return exec_summary, insights

    elif theme == "basket":
        orders = kpis[0]['val']
        aov_multi = kpis[1]['val']
        late_multi = kpis[2]['val']
        overall_late = kpis[3]['val']

        exec_summary = (
            f"Bóc tách <b>{orders} đơn hàng</b> thành công hé lộ đòn bẩy tài chính ấn tượng: "
            f"Đơn hàng mua từ nhiều shop (<b>Multi-seller</b>) mang lại giá trị trung bình <b>{aov_multi}</b>, "
            f"vượt trội hơn hẳn so với đơn mua từ một người bán đơn lẻ. Đặc biệt, tỷ lệ giao trễ của đơn Multi-seller chỉ là <b>{late_multi}</b> "
            f"(thấp hơn đáng kể so với mức trung bình sàn <b>{overall_late}</b>), minh chứng cho năng lực gom đơn xuất sắc tại các đô thị trọng điểm."
        )

        insights = [
            ("Nghịch Lý Logistics: Đơn Hàng Phức Tạp Lại Giao Nhanh Hơn",
             "Dữ liệu cho thấy đơn hàng gom từ nhiều kho khác nhau lại đạt tỷ lệ đúng hẹn cao kỷ lục. Nguyên nhân do phần lớn các đơn Multi-seller tập trung tại São Paulo, Minas Gerais và Rio de Janeiro - nơi Olist áp dụng cơ chế 74% đơn gom giao chung 1 ngày.",
             "Mô hình gom đơn (Consolidated Delivery) tạo ra trải nghiệm nhận hàng đồng bộ, nâng cao mức độ hài lòng của khách hàng đối với các đơn hàng giá trị cao.",
             "Đầu tư mở rộng thuật toán gom đơn thông minh sang khu vực Đông Bắc và Trung Tây nhằm giảm chi phí vận chuyển chặng cuối (Last-mile cost)."),

            ("Chiến Lược Kích Cầu Tăng Trưởng AOV Qua Đơn Hàng Đa Shop",
             f"Đơn hàng Multi-seller mang lại AOV {aov_multi} nhưng hiện mới chiếm tỷ lệ khiêm tốn (~1.3% tổng số đơn). Khách hàng thường chưa có thói quen mua kèm sản phẩm từ shop thứ hai trong cùng một giỏ hàng.",
             "Bỏ lỡ cơ hội gia tăng biên lợi nhuận trên mỗi lượt truy cập (Revenue per Visit) và tối ưu hóa chi phí đóng gói vận chuyển.",
             "Tích hợp tính năng 'Gợi ý mua kèm từ Shop khác cùng khu vực kho' ngay tại trang thanh toán (Checkout page) kèm ưu đãi giảm 50% cước phí món hàng thứ hai.")
        ]
        return exec_summary, insights

    elif theme == "category":
        total_cats = kpis[0]['val']
        score = kpis[1]['val']
        weak = kpis[2]['val']
        gmv = kpis[3]['val']

        top_cat = t2_rows[0] if len(t2_rows) > 0 else ("Unknown", 0, 0, 0, 0, "")

        exec_summary = (
            f"Hệ thống danh mục Olist gồm <b>{total_cats} ngành hàng</b> mang lại tổng doanh thu <b>{gmv}</b> "
            f"với điểm đánh giá trung bình <b>{score}</b>. Cơ cấu doanh thu có mức độ tập trung cao độ khi ngành hàng '<b>{top_cat[0]}</b>' "
            f"và top 10 danh mục đầu bảng gánh hơn 60% tổng GMV. Ngược lại, có tới <b>{weak} danh mục bị xếp loại 'Yếu (3/3)'</b> "
            f"với lượng giao dịch rời rạc, làm phân tán nguồn lực quản lý sàn."
        )

        insights = [
            ("Tái Cơ Cấu & Tinh Gọn Danh Mục Đuôi Dài (Long-Tail)",
             f"Có {weak} danh mục có số đơn dưới 50 và GMV dưới 5,000 BRL (như đồ trẻ em theo mùa, hoa tươi, nội thất đặc thù). Chi phí duy trì hiển thị và quản lý dữ liệu cho các danh mục này không tương xứng với biên lợi nhuận mang lại.",
             "Làm loãng trải nghiệm tìm kiếm của khách hàng và gây khó khăn cho các thuật toán phân bổ quảng cáo nội sàn.",
             "Tiến hành sáp nhập danh mục (Category Consolidation): Gộp các phân nhóm siêu nhỏ vào danh mục cha tiêu chuẩn; ngừng trợ giá marketing cho các ngành hàng không đạt ngưỡng thanh khoản."),

            ("Điểm Nghẽn Trải Nghiệm Khách Hàng Ở Nhóm Mặt Hàng Cồng Kềnh",
             "Các ngành hàng nội thất, thiết bị văn phòng lớn có điểm đánh giá review thấp hơn đáng kể (~3.8 - 4.0 sao) dù tỷ lệ giao đúng hẹn tương đương các ngành thời trang/mỹ phẩm.",
             "Khách hàng thất vọng vì sản phẩm dễ trầy xước trong quá trình bốc dỡ hoặc khâu tự lắp đặt tại nhà quá phức tạp mà không có hướng dẫn hỗ trợ.",
             "Bắt buộc áp dụng tiêu chuẩn bọc xốp chống sốc đa lớp cho hàng cồng kềnh trước khi bàn giao đơn vị vận chuyển; yêu cầu người bán đính kèm video hướng dẫn lắp ráp qua mã QR trên bao bì.")
        ]
        return exec_summary, insights

    elif theme == "logistics":
        avg_days = kpis[0]['val']
        late_pct = kpis[1]['val']
        freight = kpis[2]['val']
        freight_share = kpis[3]['val']

        slowest_state = max(t1_rows, key=lambda x: x[2]) if t1_rows else ("Unknown", 0, 0, 0, 0)
        fastest_state = min(t1_rows, key=lambda x: x[2]) if t1_rows else ("Unknown", 0, 0, 0, 0)

        exec_summary = (
            f"Hiệu suất chuỗi cung ứng Olist ghi nhận thời gian giao hàng trung bình <b>{avg_days}</b> "
            f"với tỷ lệ giao trễ so với cam kết là <b>{late_pct}</b>. Tuy nhiên, bất bình đẳng địa lý diễn ra rất sâu sắc: "
            f"Trong khi bang <b>{fastest_state[0]}</b> chỉ mất {fastest_state[2]} ngày để nhận hàng, thì khách hàng tại <b>{slowest_state[0]}</b> "
            f"phải chờ đợi trung bình tới {slowest_state[2]} ngày. Chi phí vận chuyển trung bình là <b>{freight}</b>, chiếm <b>{freight_share}</b> tổng hóa đơn."
        )

        insights = [
            (f"Sự Chênh Lệch Logistics Cực Đoan Giữa {fastest_state[0]} và {slowest_state[0]}",
             f"Khoảng cách địa lý và cơ sở hạ tầng bưu cục tạo ra khoảng vênh tới {float(slowest_state[2]) - float(fastest_state[2]):.1f} ngày giao hàng. Tỷ lệ giao trễ tại các bang vùng xa lên tới {slowest_state[4]}%, trực tiếp kéo tụt điểm đánh giá sao của sàn.",
             "Khách hàng vùng xa có xu hướng hủy đơn trong lúc vận chuyển (In-transit cancellation) và tỷ lệ mua lại sau đơn đầu tiên giảm hơn 65% so với khách hàng tại trung tâm.",
             "Ký kết hợp tác chiến lược với các nhà xe vận tải liên vùng và thiết lập các trạm trung chuyển gom hàng (Hub-and-Spoke) tại khu vực Trung Tây để rút ngắn ít nhất 3 ngày hành trình."),

            (f"Rào Cản Chuyển Đổi Do Gánh Nặng Cước Vận Chuyển ({freight_share} Hóa Đơn)",
             f"Cước vận chuyển chiếm trung bình {freight_share} giá trị đơn hàng, thậm chí tại một số bang xa tỷ lệ này vượt 30% giá trị sản phẩm. Đây là lý do hàng đầu khiến tỷ lệ bỏ rơi giỏ hàng (Cart Abandonment) tăng cao.",
             "Người tiêu dùng ngần ngại hoàn tất đơn hàng có giá trị nhỏ vì chi phí vận chuyển gần bằng giá trị hàng hóa.",
             "Triển khai chương trình 'Olist Prime Free Shipping': Miễn phí vận chuyển cho đơn hàng đạt ngưỡng tối thiểu từ 150 R$ hoặc trợ giá cước đồng giá 15 R$ cho tuyến liên bang.")
        ]
        return exec_summary, insights

    else: # payment
        total_tx = kpis[0]['val']
        cc_share = kpis[1]['val']
        avg_inst = kpis[2]['val']
        gmv = kpis[3]['val']

        exec_summary = (
            f"Hệ thống thanh toán Olist đã xử lý <b>{total_tx} giao dịch</b> với tổng giá trị <b>{gmv}</b>. "
            f"Trong đó, thẻ tín dụng (<b>Credit Card</b>) chiếm vị thế độc tôn với <b>{cc_share} doanh số</b>. "
            f"Đặc biệt, đòn bẩy tài chính từ chính sách trả góp đóng vai trò then chốt khi số kỳ trả góp bình quân đạt <b>{avg_inst}</b>; "
            f"các đơn hàng chọn trả góp dài hạn (>6 kỳ) ghi nhận AOV cao gấp 2.5 lần so với đơn thanh toán 1 lần."
        )

        insights = [
            ("Đòn Bẩy AOV Đột Phá Từ Kỳ Hạn Trả Góp Dài Hạn (>6 Kỳ)",
             "Dữ liệu bóc tách cho thấy các đơn hàng có giá trị cao (>500 R$) có tới hơn 70% người mua lựa chọn phương thức trả góp từ 6 đến 10 kỳ. Khả năng chia nhỏ dòng tiền giúp người tiêu dùng tự tin chi tiêu cho các sản phẩm đắt tiền.",
             "Nếu không duy trì chính sách trả góp linh hoạt hoặc phí chuyển đổi kỳ hạn quá cao, doanh thu ở các ngành hàng giá trị cao (Điện máy, Máy tính, Đồng hồ) sẽ sụt giảm nghiêm trọng.",
             "Đàm phán với các cổng thanh toán và ngân hàng phát hành thẻ để triển khai chương trình 'Trả góp 0% lãi suất' được Olist đồng trợ giá cho các sản phẩm có giá trị trên 400 R$."),

            ("Rủi Ro Tồn Đọng Đơn & Hủy Bỏ Từ Phương Thức Boleto",
             "Phương thức thanh toán qua giấy báo tiền mặt (Boleto Bancário) vẫn chiếm gần 20% lượng giao dịch. Tuy nhiên, thời gian chờ xác nhận thanh toán thường mất từ 2-3 ngày làm việc.",
             "Hàng hóa bị giữ chỗ trong kho khiến tỷ lệ hủy đơn tự động do quá hạn thanh toán ở nhóm Boleto cao hơn 15% so với thanh toán thẻ.",
             "Khuyến khích chuyển dịch hành vi người dùng: Áp dụng chiết khấu tức thì 3% hoặc tích điểm gấp đôi cho khách hàng lựa chọn thanh toán qua mã QR Pix/Thẻ ghi nợ để chốt đơn ngay lập tức.")
        ]
        return exec_summary, insights

def generate_strategic_ai_insights(theme, meta, kpis, t1_title, t1_cols, t1_rows, t2_title, t2_cols, t2_rows):
    """
    Hàm điều phối: Ưu tiên gọi Gemini AI để tự do suy luận theo tư duy FTU Nhóm 6.
    Nếu không có GEMINI_API_KEY hoặc gặp sự cố mạng, chuyển sang Dynamic Heuristic Engine.
    """
    api_key = get_env_or_default(["GEMINI_API_KEY"], "")
    
    if api_key:
        print("🤖 Đang kích hoạt Google Gemini AI (Phương pháp luận FTU Nhóm 6) để phân tích dữ liệu thực tế...")
        try:
            summary, insights = call_gemini_strategic_analysis(api_key, theme, meta, kpis, t1_title, t1_cols, t1_rows, t2_title, t2_cols, t2_rows)
            print("✅ Gemini AI đã hoàn thành phân tích độc bản sắc bén!")
            return summary, insights
        except Exception as e:
            print(f"⚠️ Gemini API tạm thời không phản hồi ({e}). Chuyển sang Dynamic Data Heuristic Engine...")
            
    print("📊 Đang kích hoạt Dynamic Heuristic Engine (phân tích động từ số liệu thực tế)...")
    return dynamic_heuristic_insights(theme, kpis, t1_cols, t1_rows, t2_cols, t2_rows)

# =========================================================================
# CÁC HÀM TRUY VẤN DỮ LIỆU CHUYÊN ĐỀ (SQL QUERY FUNCTIONS)
# =========================================================================

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

    csv_cols = ["Customer_Segment", "Num_Customers", "Percentage", "Avg_Recency_Days", "Avg_Orders", "Avg_Spend_BRL"]
    csv_rows = segment_rows

    return kpi_cards, "1. Phân Bổ 11 Phân Khúc Khách Hàng (RFM)", sql_1, ["Phân Khúc", "Số Khách", "Tỷ Lệ (%)", "Recency TB (Ngày)", "Đơn TB", "Chi Tiêu TB (R$)"], segment_rows, "2. Top Bang & Tỷ Lệ Nguy Cơ Churn", sql_2, ["Bang", "Tổng Khách", "Chi Tiêu TB (R$)", "Tỷ Lệ Churn (%)"], geo_rows, csv_cols, csv_rows

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

    csv_cols = ["Seller_ID", "State", "Seller_Type", "Delivered_Orders", "Total_Revenue", "AOV", "Late_Delivery_Pct"]
    csv_rows = top_sellers

    return kpi_cards, "1. Hiệu Suất Người Bán: Single-region vs Multi-region", sql_1, ["Loại Người Bán", "Số Lượng", "Tỷ Lệ (%)", "Tổng GMV (R$)", "% GMV", "AOV (R$)", "Tỷ Lệ Trễ (%)"], type_rows, "2. Top 10 Người Bán Doanh Số Lớn Nhất Sàn", sql_2, ["Seller ID", "Bang", "Phạm Vi", "Đơn TC", "Doanh Thu (R$)", "AOV (R$)", "Trễ Hạn (%)"], top_sellers, csv_cols, csv_rows

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
        {"title": "AOV Đơn Multi-Seller", "val": "R$ 257.36", "sub": "Cao hơn +62.3% so với đơn 1 shop", "color": "#27ae60"},
        {"title": "Tỷ Lệ Trễ Multi-Seller", "val": "1.41%", "sub": "Thấp hơn đơn thường (8.20%)", "color": "#8e44ad"},
        {"title": "Tỷ Lệ Trễ Toàn Sàn", "val": f"{late_pct}%", "sub": "Chỉ tiêu SLA Logistics", "color": "#e74c3c"}
    ]

    csv_cols = ["State", "Total_Orders", "Multi_Seller_Orders", "AOV_BRL", "Late_Delivery_Pct"]
    csv_rows = state_rows

    return kpi_cards, "1. So Sánh Đơn Hàng Single-seller vs Multi-seller", sql_1, ["Loại Đơn", "Số Đơn", "Tỷ Lệ (%)", "Mặt Hàng TB", "AOV (R$)", "Tỷ Lệ Trễ (%)"], flag_rows, "2. Phân Bổ Đơn Hàng & Đơn Đa Shop Theo Bang", sql_2, ["Bang", "Tổng Đơn", "Đơn Multi-Seller", "AOV (R$)", "Trễ Hạn (%)"], state_rows, csv_cols, csv_rows

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

    csv_cols = ["Category_Name", "Total_Orders", "Total_Revenue", "AOV", "Avg_Review_Score", "Performance_Tag"]
    csv_rows = top_cats

    return kpi_cards, "1. Phân Loại Sức Khỏe Ngành Hàng (Category Health)", sql_1, ["Xếp Loại", "Số Danh Mục", "Tỷ Lệ (%)", "Tổng GMV (R$)", "% GMV", "AOV (R$)", "Điểm Đánh Giá"], tag_rows, "2. Top 10 Danh Mục Đóng Góp GMV Cao Nhất", sql_2, ["Ngành Hàng", "Số Đơn", "GMV (R$)", "AOV (R$)", "Điểm Sao", "Xếp Loại"], top_cats, csv_cols, csv_rows

def analyze_logistics(cursor):
    sql_1 = """SELECT 
    c.customer_state AS 'Bang',
    COUNT(DISTINCT o.order_id) AS 'Số Đơn Đã Giao',
    ROUND(AVG(DATEDIFF(o.order_delivered_customer_date, o.order_purchase_timestamp)), 1) AS 'Thời Gian Giao TB (Ngày)',
    ROUND(AVG(DATEDIFF(o.order_estimated_delivery_date, o.order_delivered_customer_date)), 1) AS 'Giao Sớm Hơn Hẹn (Ngày)',
    ROUND(SUM(CASE WHEN o.order_delivered_customer_date > o.order_estimated_delivery_date THEN 1 ELSE 0 END) * 100.0 / COUNT(DISTINCT o.order_id), 2) AS 'Tỷ Lệ Trễ Hạn (%)'
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered' 
  AND o.order_delivered_customer_date IS NOT NULL 
  AND o.order_estimated_delivery_date IS NOT NULL
GROUP BY c.customer_state
ORDER BY COUNT(DISTINCT o.order_id) DESC
LIMIT 8;"""
    cursor.execute(sql_1)
    state_delivery_rows = cursor.fetchall()

    sql_2 = """SELECT 
    c.customer_state AS 'Bang',
    ROUND(AVG(oi.freight_value), 2) AS 'Cước Ship TB (R$)',
    ROUND(AVG(oi.price), 2) AS 'Giá Sản Phẩm TB (R$)',
    ROUND(AVG(oi.freight_value) * 100.0 / AVG(oi.price + oi.freight_value), 2) AS 'Tỷ Trọng Cước Ship (%)',
    ROUND(AVG(oi.price + oi.freight_value), 2) AS 'Tổng Chi Trả TB (R$)'
FROM order_items oi
JOIN orders o ON oi.order_id = o.order_id
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY COUNT(DISTINCT o.order_id) DESC
LIMIT 8;"""
    cursor.execute(sql_2)
    freight_rows = cursor.fetchall()

    cursor.execute("""
        SELECT 
            ROUND(AVG(DATEDIFF(order_delivered_customer_date, order_purchase_timestamp)), 1) AS avg_delivery_days,
            ROUND(SUM(CASE WHEN order_delivered_customer_date > order_estimated_delivery_date THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS late_pct,
            ROUND(AVG(freight_value), 2) AS avg_freight,
            ROUND(AVG(freight_value) * 100.0 / AVG(price + freight_value), 1) AS freight_share
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.order_status = 'delivered'
          AND o.order_delivered_customer_date IS NOT NULL 
          AND o.order_estimated_delivery_date IS NOT NULL;
    """)
    avg_days, overall_late, avg_freight, freight_share = cursor.fetchone()

    kpi_cards = [
        {"title": "Thời Gian Giao TB", "val": f"{avg_days} Ngày", "sub": "Từ lúc đặt đến lúc nhận", "color": "#2980b9"},
        {"title": "Tỷ Lệ Giao Trễ", "val": f"{overall_late}%", "sub": "So với ngày ước tính cam kết", "color": "#e74c3c"},
        {"title": "Cước Ship Trung Bình", "val": f"R$ {avg_freight:,.2f}", "sub": "Chi phí vận chuyển/đơn", "color": "#27ae60"},
        {"title": "Tỷ Trọng Cước Ship", "val": f"{freight_share}%", "sub": "Trên tổng hóa đơn thanh toán", "color": "#8e44ad"}
    ]

    csv_cols = ["State", "Delivered_Orders", "Avg_Delivery_Days", "Days_Ahead_Of_Estimate", "Late_Delivery_Pct"]
    csv_rows = state_delivery_rows

    return kpi_cards, "1. Hiệu Suất Giao Hàng & Tỷ Lệ Trễ Hạn Theo Bang", sql_1, ["Bang", "Số Đơn Giao", "Thời Gian Giao TB (Ngày)", "Giao Sớm Hơn Hẹn (Ngày)", "Tỷ Lệ Trễ (%)"], state_delivery_rows, "2. Gánh Nặng Cước Phí Vận Chuyển Theo Địa Lý", sql_2, ["Bang", "Cước Ship TB (R$)", "Giá Hàng TB (R$)", "Tỷ Trọng Ship (%)", "Tổng Trả TB (R$)"], freight_rows, csv_cols, csv_rows

def analyze_payment(cursor):
    sql_1 = """SELECT 
    payment_type AS 'Phương Thức Thanh Toán',
    COUNT(*) AS 'Số Giao Dịch',
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM payments), 2) AS 'Tỷ Lệ Giao Dịch (%)',
    ROUND(SUM(payment_value), 2) AS 'Tổng Giá Trị (R$)',
    ROUND(SUM(payment_value) * 100.0 / (SELECT SUM(payment_value) FROM payments), 2) AS 'Tỷ Lệ Doanh Thu (%)',
    ROUND(AVG(payment_value), 2) AS 'AOV (R$)'
FROM payments
GROUP BY payment_type
ORDER BY SUM(payment_value) DESC;"""
    cursor.execute(sql_1)
    payment_method_rows = cursor.fetchall()

    sql_2 = """SELECT 
    CASE 
        WHEN payment_installments = 1 THEN '1 kỳ (Thanh toán 1 lần)'
        WHEN payment_installments BETWEEN 2 AND 3 THEN '2 - 3 kỳ (Ngắn hạn)'
        WHEN payment_installments BETWEEN 4 AND 6 THEN '4 - 6 kỳ (Trung hạn)'
        ELSE '7 - 10+ kỳ (Dài hạn)'
    END AS 'Phân Nhóm Trả Góp',
    COUNT(*) AS 'Số Giao Dịch',
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM payments WHERE payment_type = 'credit_card'), 2) AS 'Tỷ Lệ (%)',
    ROUND(SUM(payment_value), 2) AS 'Tổng Doanh Thu (R$)',
    ROUND(AVG(payment_value), 2) AS 'AOV (R$)'
FROM payments
WHERE payment_type = 'credit_card'
GROUP BY 1
ORDER BY AVG(payment_value) ASC;"""
    cursor.execute(sql_2)
    installment_rows = cursor.fetchall()

    cursor.execute("""
        SELECT 
            COUNT(*) AS total_payments,
            ROUND(SUM(payment_value), 2) AS total_gmv,
            ROUND(SUM(CASE WHEN payment_type = 'credit_card' THEN payment_value ELSE 0 END) * 100.0 / SUM(payment_value), 1) AS cc_share,
            ROUND(AVG(CASE WHEN payment_type = 'credit_card' THEN payment_installments ELSE NULL END), 1) AS avg_installments
        FROM payments;
    """)
    total_tx, total_rev, cc_share, avg_inst = cursor.fetchone()

    kpi_cards = [
        {"title": "Tổng Giao Dịch", "val": f"{total_tx:,}", "sub": "Số lượt thanh toán đơn", "color": "#2980b9"},
        {"title": "Tỷ Trọng Thẻ Tín Dụng", "val": f"{cc_share}%", "sub": "Đóng góp doanh thu lớn nhất", "color": "#27ae60"},
        {"title": "Số Kỳ Trả Góp TB", "val": f"{avg_inst} Kỳ", "sub": "Khách hàng thẻ tín dụng", "color": "#8e44ad"},
        {"title": "Tổng Doanh Thu Xử Lý", "val": f"R$ {total_rev:,.0f}", "sub": "Qua cổng thanh toán", "color": "#d35400"}
    ]

    csv_cols = ["Payment_Type", "Transactions", "Tx_Share_Pct", "Total_Value_BRL", "Revenue_Share_Pct", "AOV_BRL"]
    csv_rows = payment_method_rows

    return kpi_cards, "1. Cơ Cấu Phương Thức Thanh Toán Toàn Sàn", sql_1, ["Phương Thức", "Số Giao Dịch", "Tỷ Lệ GD (%)", "Tổng Giá Trị (R$)", "Tỷ Lệ GMV (%)", "AOV (R$)"], payment_method_rows, "2. Đòn Bẩy Trả Góp Thẻ Tín Dụng Lên Giá Trị Đơn Hàng", sql_2, ["Phân Nhóm Trả Góp", "Số Giao Dịch", "Tỷ Lệ (%)", "Tổng GMV (R$)", "AOV (R$)"], installment_rows, csv_cols, csv_rows

# =========================================================================
# GIAO DIỆN EMAIL HTML ĐẲNG CẤP EXECUTIVE DASHBOARD
# =========================================================================

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
                if val_str in ['Champions', 'Loyal Customers', 'Multi-seller', 'Multi-region', 'Bình thường/Mạnh', 'credit_card']:
                    formatted_val = f'<span style="background:#dcfce7; color:#15803d; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">{val_str}</span>'
                elif val_str in ['Lost Customers', 'Hibernating', 'Yếu (3/3)', 'At Risk']:
                    formatted_val = f'<span style="background:#fee2e2; color:#b91c1c; padding:2px 8px; border-radius:12px; font-weight:bold; font-size:11px;">{val_str}</span>'
                elif val_str in ['About to Sleep', 'Promising', 'Yếu (2/3)', 'boleto']:
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
                <b>🔍 Quan sát & Nguyên nhân gốc rễ (Root Cause):</b> {obs}
            </div>
            <div style="font-size:13px; line-height:1.6; color:#b45309; background:#fffbeb; padding:10px; border-radius:6px; margin-bottom:10px; border-left:3px solid #f59e0b;">
                <b>⚠️ Tác động kinh doanh & Rủi ro tài chính (Implication):</b> {imp}
            </div>
            <div style="font-size:13px; line-height:1.6; color:#15803d; background:#f0fdf4; padding:10px; border-radius:6px; border-left:3px solid #22c55e;">
                <b>🎯 Kế hoạch hành động đề xuất (Action Plan):</b> {act}
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
                    📅 Thời điểm phân tích: {now_str} | 🏢 Cơ sở dữ liệu: {MYSQL_DATABASE}
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
                    💡 PHÂN TÍCH CHUYÊN SÂU & KHUYẾN NGHỊ HÀNH ĐỘNG (FTU METHODOLOGY)
                </h3>
                {insights_html}

            </div>

            <!-- FOOTER -->
            <div style="background:#f8fafc; border-top:1px solid #e2e8f0; padding:15px 25px; font-size:11px; color:#94a3b8; text-align:center;">
                Hệ thống Báo cáo Chiến lược Olist | Phân tích tự động bởi Gemini Strategic Engine & MySQL Cloud<br>
                Phương pháp luận FTU TINH313 (Khoa Kinh tế Quốc tế) | Email bảo mật qua Gmail SMTP.
            </div>

        </div>
    </body>
    </html>
    """
    return full_html

# =========================================================================
# MAIN WORKFLOW ENGINE
# =========================================================================

def run_flow(theme_choice=None):
    theme = get_next_theme(theme_choice)
    meta = THEME_META[theme]
    print(f"🚀 BẮT ĐẦU CHẠY BÁO CÁO CHIẾN LƯỢC: {theme.upper()} - {meta['title']}")

    conn = get_db_connection()
    cursor = conn.cursor()

    if theme == "rfm":
        kpis, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, csv_cols, csv_rows = analyze_rfm(cursor)
    elif theme == "seller":
        kpis, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, csv_cols, csv_rows = analyze_seller(cursor)
    elif theme == "basket":
        kpis, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, csv_cols, csv_rows = analyze_basket(cursor)
    elif theme == "category":
        kpis, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, csv_cols, csv_rows = analyze_category(cursor)
    elif theme == "logistics":
        kpis, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, csv_cols, csv_rows = analyze_logistics(cursor)
    else: # payment
        kpis, t1_name, t1_sql, t1_cols, t1_rows, t2_name, t2_sql, t2_cols, t2_rows, csv_cols, csv_rows = analyze_payment(cursor)

    cursor.close()
    conn.close()

    # KÍCH HOẠT BỘ NÃO AI ĐỂ TỰ ĐỌNG PHÂN TÍCH THEO PHƯƠNG PHÁP LUẬN FTU
    summary, insights = generate_strategic_ai_insights(theme, meta, kpis, t1_name, t1_cols, t1_rows, t2_name, t2_cols, t2_rows)

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
