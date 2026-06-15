```python
import os
from io import BytesIO
from textwrap import wrap

import pandas as pd
import requests
import streamlit as st
from PIL import Image, ImageDraw, ImageFont


# =========================
# 기본 설정
# =========================
st.set_page_config(
    page_title="장보기 미션 앱",
    page_icon="🛒",
    layout="wide"
)

MISSIONS = {
    "카레 만들기": 18000,
    "여름캠핑 준비하기": 35000,
    "친구 생일파티 준비하기": 30000,
}

CSV_PATH = "products.csv"


# =========================
# 세션 상태 초기화
# =========================
def init_state():
    if "page" not in st.session_state:
        st.session_state.page = "start"

    if "mission" not in st.session_state:
        st.session_state.mission = None

    if "budget" not in st.session_state:
        st.session_state.budget = 0

    if "cart" not in st.session_state:
        st.session_state.cart = {}

    if "quantities" not in st.session_state:
        st.session_state.quantities = {}

    if "submitted" not in st.session_state:
        st.session_state.submitted = False


init_state()


# =========================
# 스타일
# =========================
st.markdown(
    """
    <style>
    .main-title {
        font-size: 40px;
        font-weight: 800;
        color: #1f5fbf;
        margin-bottom: 4px;
    }
    .sub-text {
        font-size: 18px;
        color: #555;
        margin-bottom: 25px;
    }
    .mission-card {
        padding: 18px;
        border-radius: 18px;
        background-color: #eef6ff;
        border: 1px solid #cfe5ff;
        margin-bottom: 12px;
    }
    .product-card {
        padding: 16px;
        border: 1px solid #e5e7eb;
        border-radius: 18px;
        background-color: white;
        min-height: 410px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    }
    .cart-box {
        padding: 18px;
        border-radius: 18px;
        background-color: #fff8d7;
        border: 1px solid #f3df8b;
    }
    .warning-box {
        padding: 14px;
        border-radius: 14px;
        background-color: #ffe5e5;
        border: 1px solid #ffb3b3;
        color: #9b1c1c;
        font-weight: 700;
    }
    .success-box {
        padding: 14px;
        border-radius: 14px;
        background-color: #e6f7e6;
        border: 1px solid #b7e3b7;
        color: #176b17;
        font-weight: 700;
    }
    </style>
    """,
    unsafe_allow_html=True
)


# =========================
# 데이터 불러오기
# =========================
@st.cache_data
def load_products():
    if not os.path.exists(CSV_PATH):
        st.error("products.csv 파일이 없습니다. app.py와 같은 폴더에 products.csv 파일을 올려 주세요.")
        st.stop()

    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]

    required_cols = ["품명", "가격", "이미지 url"]
    missing = [c for c in required_cols if c not in df.columns]

    if missing:
        st.error(f"products.csv에 다음 열이 필요합니다: {', '.join(required_cols)}")
        st.stop()

    df["가격"] = pd.to_numeric(df["가격"], errors="coerce").fillna(0).astype(int)
    df["품명"] = df["품명"].astype(str)
    df["이미지 url"] = df["이미지 url"].astype(str)

    return df


def money(value):
    return f"{value:,}원"


def get_cart_total(products_df):
    total = 0
    for name, qty in st.session_state.cart.items():
        row = products_df[products_df["품명"] == name]
        if not row.empty:
            price = int(row.iloc[0]["가격"])
            total += price * qty
    return total


def reset_shopping(mission):
    st.session_state.mission = mission
    st.session_state.budget = MISSIONS[mission]
    st.session_state.cart = {}
    st.session_state.quantities = {}
    st.session_state.submitted = False
    st.session_state.page = "shop"


# =========================
# 결과 이미지 생성용 함수
# =========================
def download_font_if_needed():
    font_dir = ".streamlit_fonts"
    os.makedirs(font_dir, exist_ok=True)
    font_path = os.path.join(font_dir, "NotoSansKR-Regular.ttf")

    if os.path.exists(font_path):
        return font_path

    font_url = "https://github.com/google/fonts/raw/main/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"

    try:
        response = requests.get(font_url, timeout=10)
        if response.status_code == 200:
            with open(font_path, "wb") as f:
                f.write(response.content)
            return font_path
    except Exception:
        pass

    return None


def get_korean_font(size):
    candidate_paths = [
        "C:/Windows/Fonts/malgun.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    ]

    for path in candidate_paths:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)

    downloaded_font = download_font_if_needed()
    if downloaded_font and os.path.exists(downloaded_font):
        return ImageFont.truetype(downloaded_font, size)

    return ImageFont.load_default()


def fetch_product_image(url, size=(120, 120)):
    try:
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img.thumbnail(size)
        canvas = Image.new("RGB", size, "white")
        x = (size[0] - img.width) // 2
        y = (size[1] - img.height) // 2
        canvas.paste(img, (x, y))
        return canvas
    except Exception:
        placeholder = Image.new("RGB", size, "#eeeeee")
        draw = ImageDraw.Draw(placeholder)
        font = get_korean_font(16)
        draw.text((22, 48), "이미지 없음", fill="#777777", font=font)
        return placeholder


def draw_wrapped_text(draw, text, xy, font, fill, max_chars, line_gap=8):
    x, y = xy
    lines = []

    for paragraph in text.split("\n"):
        if paragraph.strip() == "":
            lines.append("")
        else:
            lines.extend(wrap(paragraph, width=max_chars))

    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap

    return y


def create_result_image(products_df, mission, budget, cart, reason):
    width = 1100
    base_height = 650 + len(cart) * 150 + max(160, len(reason) * 4)
    height = min(max(base_height, 900), 2200)

    img = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(img)

    title_font = get_korean_font(44)
    sub_font = get_korean_font(28)
    body_font = get_korean_font(24)
    small_font = get_korean_font(20)

    # 상단 배경
    draw.rounded_rectangle((40, 35, width - 40, 140), radius=30, fill="#eaf4ff")
    draw.text((75, 65), f"미션: {mission}", fill="#1f5fbf", font=title_font)

    y = 180
    total = 0

    draw.text((60, y), "내가 고른 물건", fill="#222222", font=sub_font)
    y += 50

    for name, qty in cart.items():
        row = products_df[products_df["품명"] == name]
        if row.empty:
            continue

        price = int(row.iloc[0]["가격"])
        image_url = row.iloc[0]["이미지 url"]
        subtotal = price * qty
        total += subtotal

        draw.rounded_rectangle((55, y, width - 55, y + 130), radius=20, fill="#f8fafc", outline="#d9e2ec")

        product_img = fetch_product_image(image_url, size=(105, 105))
        img.paste(product_img, (80, y + 12))

        draw.text((215, y + 18), name, fill="#222222", font=body_font)
        draw.text((215, y + 58), f"수량: {qty}개", fill="#444444", font=small_font)
        draw.text((430, y + 58), f"가격: {money(price)}", fill="#444444", font=small_font)
        draw.text((680, y + 58), f"합계: {money(subtotal)}", fill="#1f5fbf", font=small_font)

        y += 150

    remaining = budget - total

    y += 10
    draw.rounded_rectangle((55, y, width - 55, y + 120), radius=22, fill="#fff8d7", outline="#ead77b")
    draw.text((80, y + 25), f"예산: {money(budget)}", fill="#333333", font=body_font)
    draw.text((360, y + 25), f"사용한 금액: {money(total)}", fill="#333333", font=body_font)
    draw.text((720, y + 25), f"남은 돈: {money(remaining)}", fill="#d97706", font=body_font)

    y += 160
    draw.text((60, y), "구매 이유", fill="#222222", font=sub_font)
    y += 45

    draw.rounded_rectangle((55, y, width - 55, height - 70), radius=22, fill="#f9fafb", outline="#d1d5db")
    draw_wrapped_text(
        draw=draw,
        text=reason,
        xy=(85, y + 30),
        font=body_font,
        fill="#333333",
        max_chars=34,
        line_gap=10
    )

    output = BytesIO()
    img.save(output, format="PNG")
    output.seek(0)
    return output


# =========================
# 시작 화면
# =========================
def show_start_page():
    st.markdown('<div class="main-title">🛒 장보기 미션 앱</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-text">정해진 예산 안에서 필요한 물건을 고르고, 왜 골랐는지 설명해 보세요.</div>',
        unsafe_allow_html=True
    )

    st.markdown("### 1단계: 오늘의 미션을 선택하세요")

    mission = st.radio(
        "미션 선택",
        list(MISSIONS.keys()),
        format_func=lambda x: f"{x} - 예산 {money(MISSIONS[x])}"
    )

    st.markdown(
        f"""
        <div class="mission-card">
        <b>선택한 미션:</b> {mission}<br>
        <b>사용할 수 있는 예산:</b> {money(MISSIONS[mission])}
        </div>
        """,
        unsafe_allow_html=True
    )

    if st.button("미션 시작하기", type="primary"):
        reset_shopping(mission)
        st.rerun()


# =========================
# 쇼핑 화면
# =========================
def show_shop_page():
    products_df = load_products()

    st.markdown(f'<div class="main-title">🛍️ 쇼핑하기: {st.session_state.mission}</div>', unsafe_allow_html=True)

    total = get_cart_total(products_df)
    remaining = st.session_state.budget - total

    top1, top2, top3 = st.columns(3)
    top1.metric("예산", money(st.session_state.budget))
    top2.metric("현재 사용 금액", money(total))
    top3.metric("남은 돈", money(remaining))

    if total > st.session_state.budget:
        st.markdown(
            '<div class="warning-box">예산을 초과했어요! 물건 수량을 줄이거나 다른 물건을 선택해 주세요.</div>',
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            '<div class="success-box">아직 예산 안에 있어요. 신중하게 장바구니를 완성해 보세요!</div>',
            unsafe_allow_html=True
        )

    st.divider()
    st.markdown("### 상품 목록")

    cols_per_row = 3
    rows = [
        products_df.iloc[i:i + cols_per_row]
        for i in range(0, len(products_df), cols_per_row)
    ]

    for row_df in rows:
        cols = st.columns(cols_per_row)

        for col, (_, product) in zip(cols, row_df.iterrows()):
            name = product["품명"]
            price = int(product["가격"])
            image_url = product["이미지 url"]

            qty_key = f"qty_{name}"
            if qty_key not in st.session_state.quantities:
                st.session_state.quantities[qty_key] = 0

            with col:
                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                st.image(image_url, use_container_width=True)
                st.markdown(f"#### {name}")
                st.markdown(f"**가격:** {money(price)}")

                c1, c2, c3 = st.columns([1, 1, 2])

                with c1:
                    if st.button("➖", key=f"minus_{name}"):
                        st.session_state.quantities[qty_key] = max(
                            0,
                            st.session_state.quantities[qty_key] - 1
                        )
                        st.rerun()

                with c2:
                    if st.button("➕", key=f"plus_{name}"):
                        st.session_state.quantities[qty_key] += 1
                        st.rerun()

                with c3:
                    st.markdown(
                        f"<p style='font-size:20px; font-weight:700;'>수량: {st.session_state.quantities[qty_key]}개</p>",
                        unsafe_allow_html=True
                    )

                if st.button("장바구니 담기", key=f"add_{name}", use_container_width=True):
                    qty = st.session_state.quantities[qty_key]
                    if qty > 0:
                        st.session_state.cart[name] = qty
                        st.success(f"{name} {qty}개를 장바구니에 담았어요!")
                    else:
                        st.warning("수량을 1개 이상 선택해 주세요.")

                st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    st.markdown("### 🧺 장바구니")

    if len(st.session_state.cart) == 0:
        st.info("아직 장바구니가 비어 있어요.")
    else:
        cart_rows = []

        for name, qty in st.session_state.cart.items():
            row = products_df[products_df["품명"] == name]
            if not row.empty:
                price = int(row.iloc[0]["가격"])
                cart_rows.append(
                    {
                        "품명": name,
                        "수량": qty,
                        "개당 가격": money(price),
                        "합계": money(price * qty),
                    }
                )

        st.dataframe(pd.DataFrame(cart_rows), use_container_width=True, hide_index=True)

    total = get_cart_total(products_df)
    remaining = st.session_state.budget - total

    st.markdown(
        f"""
        <div class="cart-box">
        <b>사용한 금액:</b> {money(total)}<br>
        <b>남은 돈:</b> {money(remaining)}
        </div>
        """,
        unsafe_allow_html=True
    )

    over_budget = total > st.session_state.budget
    empty_cart = len(st.session_state.cart) == 0

    if over_budget:
        st.warning("예산을 초과했기 때문에 제출할 수 없어요.")
    elif empty_cart:
        st.warning("장바구니에 물건을 담아야 제출할 수 있어요.")

    col_a, col_b = st.columns([1, 1])

    with col_a:
        if st.button("처음으로 돌아가기"):
            st.session_state.page = "start"
            st.rerun()

    with col_b:
        submitted = st.button(
            "제출하기",
            type="primary",
            disabled=over_budget or empty_cart,
            use_container_width=True
        )

        if submitted:
            st.session_state.submitted = True
            st.session_state.page = "result"
            st.rerun()


# =========================
# 결과 화면
# =========================
def show_result_page():
    if not st.session_state.submitted:
        st.session_state.page = "shop"
        st.rerun()

    products_df = load_products()

    st.markdown(f'<div class="main-title">🎉 결과 화면: {st.session_state.mission}</div>', unsafe_allow_html=True)

    total = get_cart_total(products_df)
    remaining = st.session_state.budget - total

    st.metric("사용한 금액", money(total))
    st.metric("남은 돈", money(remaining))

    st.divider()
    st.markdown("### 내가 구매한 물건")

    for name, qty in st.session_state.cart.items():
        row = products_df[products_df["품명"] == name]

        if row.empty:
            continue

        price = int(row.iloc[0]["가격"])
        image_url = row.iloc[0]["이미지 url"]

        col1, col2 = st.columns([1, 4])

        with col1:
            st.image(image_url, use_container_width=True)

        with col2:
            st.markdown(f"#### {name}")
            st.markdown(f"- 수량: **{qty}개**")
            st.markdown(f"- 개당 가격: **{money(price)}**")
            st.markdown(f"- 합계: **{money(price * qty)}**")

    st.divider()
    st.markdown("### 구매 이유 쓰기")
    reason = st.text_area(
        "내가 이 물건들을 고른 이유를 써 보세요.",
        height=180,
        placeholder="예: 카레를 만들기 위해 감자, 당근, 카레가루가 꼭 필요해서 골랐습니다."
    )

    if reason.strip():
        result_image = create_result_image(
            products_df=products_df,
            mission=st.session_state.mission,
            budget=st.session_state.budget,
            cart=st.session_state.cart,
            reason=reason.strip()
        )

        st.download_button(
            label="그림으로 저장",
            data=result_image,
            file_name=f"{st.session_state.mission}_장보기_미션_결과.png",
            mime="image/png",
            type="primary"
        )
    else:
        st.info("구매 이유를 작성하면 '그림으로 저장' 버튼이 나타나요.")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        if st.button("쇼핑 화면으로 돌아가기"):
            st.session_state.page = "shop"
            st.rerun()

    with col2:
        if st.button("새 미션 시작하기"):
            st.session_state.page = "start"
            st.session_state.mission = None
            st.session_state.budget = 0
            st.session_state.cart = {}
            st.session_state.quantities = {}
            st.session_state.submitted = False
            st.rerun()


# =========================
# 라우팅
# =========================
if st.session_state.page == "start":
    show_start_page()
elif st.session_state.page == "shop":
    show_shop_page()
elif st.session_state.page == "result":
    show_result_page()
else:
    st.session_state.page = "start"
    st.rerun()
```
