import streamlit as st
import re
import requests
import io
import time
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

# Set Streamlit Page Configuration
st.set_page_config(
    page_title="Gerador de Proxies MTG",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for rich aesthetics (dark mode inspired, neon accents, beautiful typography)
st.markdown("""
<style>
    /* Styling elements */
    .main-title {
        font-family: 'Outfit', 'Inter', sans-serif;
        font-size: 3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
        text-align: center;
    }
    .subtitle {
        font-family: 'Inter', sans-serif;
        font-size: 1.1rem;
        color: #94a3b8;
        margin-bottom: 2rem;
        text-align: center;
    }
    .card-preview-container {
        background-color: #1e293b;
        border-radius: 12px;
        padding: 15px;
        margin-bottom: 15px;
        border: 1px solid #334155;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
    }
    .card-title {
        font-weight: 600;
        color: #f8fafc;
        margin-top: 10px;
        font-size: 0.95rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .card-qty {
        color: #38bdf8;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .card-edition {
        color: #a855f7;
        font-size: 0.85rem;
        font-weight: bold;
    }
    .stButton>button {
        background: linear-gradient(135deg, #a855f7 0%, #6366f1 100%) !important;
        color: white !important;
        border: none !important;
        font-weight: 600 !important;
        padding: 0.6rem 2rem !important;
        border-radius: 8px !important;
        transition: transform 0.2s, box-shadow 0.2s !important;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px rgba(168, 85, 247, 0.4);
    }
    .instructions {
        background-color: #0f172a;
        padding: 20px;
        border-radius: 12px;
        border-left: 5px solid #a855f7;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

def parse_decklist(texto):
    """
    Parses a decklist string line by line.
    Supported formats:
    4 Lightning Bolt (LEA)
    1 Black Lotus (LEB) 23
    4x Brainstorm (CNS)
    1 Sol Ring
    
    Returns a list of dicts: [{'quantity': int, 'name': str, 'set_code': str or None}]
    """
    cards = []
    # Match quantity, name, optional set code, and optional collector number
    pattern = re.compile(
        r'^\s*(?P<quantity>\d+)\s*x?\s+(?P<name>[^(]+?)(?:\s*\((?P<set>[^)]+)\))?(?:\s+\d+)?\s*$',
        re.IGNORECASE
    )
    
    for line in texto.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('//') or line.startswith('#'):
            continue
            
        match = pattern.match(line)
        if match:
            gd = match.groupdict()
            cards.append({
                'quantity': int(gd['quantity']),
                'name': gd['name'].strip(),
                'set_code': gd['set'].strip().upper() if gd['set'] else None
            })
        else:
            # Fallback to simple quantity and name extract
            fallback_pattern = re.compile(r'^\s*(?P<quantity>\d+)\s*x?\s+(?P<name>.+)$', re.IGNORECASE)
            fallback_match = fallback_pattern.match(line)
            if fallback_match:
                gd = fallback_match.groupdict()
                cards.append({
                    'quantity': int(gd['quantity']),
                    'name': gd['name'].strip(),
                    'set_code': None
                })
    return cards

def fetch_card_image(name, set_code=None):
    """
    Queries the Scryfall API to retrieve the card image in normal or large size.
    Returns: A PIL Image object if successful, else None.
    """
    time.sleep(0.1)  # Respect Scryfall Rate Limit (50-100ms)
    
    headers = {
        "User-Agent": "MTGProxyPrintApp/1.0 (contact@example.com)",
        "Accept": "application/json"
    }
    
    # 1. Try Exact match endpoint
    url = f"https://api.scryfall.com/cards/named?exact={requests.utils.quote(name)}"
    if set_code:
        url += f"&set={requests.utils.quote(set_code)}"
        
    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        # 2. Try Fuzzy match endpoint if exact fails
        if response.status_code != 200:
            fuzzy_url = f"https://api.scryfall.com/cards/named?fuzzy={requests.utils.quote(name)}"
            if set_code:
                fuzzy_url += f"&set={requests.utils.quote(set_code)}"
            response = requests.get(fuzzy_url, headers=headers, timeout=10)
            
        if response.status_code == 200:
            data = response.json()
            # Handle standard single-faced cards or front-face of double-faced cards
            image_uris = data.get('image_uris')
            if not image_uris and 'card_faces' in data:
                image_uris = data['card_faces'][0].get('image_uris')
                
            if image_uris:
                image_url = image_uris.get('large') or image_uris.get('normal')
                if image_url:
                    img_response = requests.get(image_url, headers=headers, timeout=10)
                    if img_response.status_code == 200:
                        return Image.open(io.BytesIO(img_response.content))
        return None
    except Exception:
        return None

def generate_pdf(card_images):
    """
    Generates a printable A4 PDF from list of PIL Image items.
    Layout: 3x3 grid (9 cards per page), centered.
    Card Size: 63mm x 88mm
    """
    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    
    card_width = 63 * mm
    card_height = 88 * mm
    
    # Margins calculations to center the grid on A4 sheet
    margin_x = (210 * mm - 3 * card_width) / 2
    margin_y = (297 * mm - 3 * card_height) / 2
    
    for idx, card_img in enumerate(card_images):
        page_idx = idx % 9
        col = page_idx % 3
        row = page_idx // 3
        
        # Positioning calculation
        x = margin_x + col * card_width
        y = margin_y + (2 - row) * card_height
        
        # Stream image directly to PDF
        img_buffer = io.BytesIO()
        card_img.save(img_buffer, format="JPEG", quality=95)
        img_buffer.seek(0)
        img_reader = ImageReader(img_buffer)
        
        c.drawImage(img_reader, x, y, width=card_width, height=card_height)
        
        # Draw cutting outline helper border
        c.setStrokeColorRGB(0.8, 0.8, 0.8)
        c.setLineWidth(0.5)
        c.rect(x, y, card_width, card_height)
        
        if page_idx == 8 and idx < len(card_images) - 1:
            c.showPage()
            
    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer

# Main UI Structure
st.markdown('<div class="main-title">Gerador de Proxies MTG</div>', unsafe_allow_html=True)
st.markdown('<div class="subtitle">Insira sua decklist, busque as imagens na Scryfall e gere um PDF A4 pronto para impressão com tamanho real</div>', unsafe_allow_html=True)

# Layout division
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.markdown("### 📋 Sua Lista de Cartas")
    
    st.markdown("""
    <div class="instructions">
        <strong>Instruções de formatação:</strong><br>
        Insira uma carta por linha no formato: <code>[Quantidade] [Nome da Carta] ([Edição])</code><br><br>
        <strong>Exemplos:</strong><br>
        <code>4 Lightning Bolt (LEA)</code><br>
        <code>1 Black Lotus (LEB) 23</code><br>
        <code>2x Sol Ring</code>
    </div>
    """, unsafe_allow_html=True)
    
    default_text = "4 Lightning Bolt (LEA)\n1 Black Lotus (LEB) 23\n2x Sol Ring\n1 Delver of Secrets (ISD)"
    decklist_text = st.text_area(
        "Cole sua lista aqui:",
        value=default_text,
        height=300,
        placeholder="Cole suas cartas..."
    )
    
    generate_btn = st.button("Gerar PDF de Proxies")

with right_col:
    st.markdown("### 🖼️ Visualização & Status")
    
    if generate_btn:
        if not decklist_text.strip():
            st.error("A lista de cartas está vazia.")
        else:
            parsed_cards = parse_decklist(decklist_text)
            
            if not parsed_cards:
                st.error("Nenhuma carta válida foi encontrada na lista. Verifique a formatação.")
            else:
                progress_text = st.empty()
                progress_bar = st.progress(0)
                
                fetched_images = []
                failed_cards = []
                
                total_to_fetch = len(parsed_cards)
                
                for i, card in enumerate(parsed_cards):
                    progress_text.text(f"Buscando '{card['name']}' no Scryfall...")
                    progress_bar.progress((i + 1) / total_to_fetch)
                    
                    img = fetch_card_image(card['name'], card['set_code'])
                    if img:
                        # Append the image multiplied by its quantity
                        for _ in range(card['quantity']):
                            fetched_images.append({
                                'image': img,
                                'name': card['name'],
                                'set_code': card['set_code']
                            })
                    else:
                        failed_cards.append(f"{card['quantity']}x {card['name']}" + (f" ({card['set_code']})" if card['set_code'] else ""))
                
                progress_bar.empty()
                progress_text.empty()
                
                if failed_cards:
                    st.warning("⚠️ Algumas cartas não puderam ser encontradas:")
                    for failed in failed_cards:
                        st.markdown(f"- **{failed}**")
                        
                if not fetched_images:
                    st.error("Nenhuma imagem de carta foi obtida. O PDF não pôde ser gerado.")
                else:
                    st.success(f"Sucesso! {len(fetched_images)} cartas preparadas para impressão.")
                    
                    # Generate PDF in memory
                    with st.spinner("Gerando PDF..."):
                        # Extract the raw PIL Images from list of dicts
                        images_only = [item['image'] for item in fetched_images]
                        pdf_data = generate_pdf(images_only)
                    
                    # Download button
                    st.download_button(
                        label="⬇️ Baixar PDF de Proxies (A4)",
                        data=pdf_data,
                        file_name="proxies.pdf",
                        mime="application/pdf"
                    )
                    
                    # Show visual grid of fetched cards
                    st.markdown("#### Pré-visualização das cartas:")
                    grid_cols = st.columns(4)
                    
                    # Group unique images for visual display
                    displayed_uniques = set()
                    unique_img_idx = 0
                    
                    for card in fetched_images:
                        unique_key = f"{card['name']}_{card['set_code']}"
                        if unique_key not in displayed_uniques:
                            displayed_uniques.add(unique_key)
                            col_to_use = grid_cols[unique_img_idx % 4]
                            
                            with col_to_use:
                                st.markdown(f"""
                                <div class="card-preview-container">
                                    <div class="card-qty">Quantidade: {card['image'] and fetched_images.count(card)}x</div>
                                    <div class="card-title" title="{card['name']}">{card['name']}</div>
                                    <div class="card-edition">{card['set_code'] if card['set_code'] else 'Padrão'}</div>
                                </div>
                                """, unsafe_allow_html=True)
                                col_to_use.image(card['image'], use_container_width=True)
                            
                            unique_img_idx += 1
    else:
        st.info("Insira a lista ao lado e clique em **Gerar PDF de Proxies**.")
