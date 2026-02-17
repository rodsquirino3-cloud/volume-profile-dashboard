import streamlit as st
import pandas as pd
import numpy as np
from binance.client import Client
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

# Configuração da página
st.set_page_config(
    page_title="Volume Profile Crypto Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS customizado
st.markdown("""
    <style>
    .big-font {
        font-size:30px !important;
        font-weight: bold;
    }
    .metric-card {
        background-color: #0e1117;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #262730;
    }
    .alert-box {
        padding: 15px;
        border-radius: 5px;
        margin: 10px 0;
    }
    .alert-danger {
        background-color: #ff4b4b;
        color: white;
    }
    .alert-warning {
        background-color: #ffa500;
        color: white;
    }
    .alert-success {
        background-color: #00cc00;
        color: white;
    }
    </style>
""", unsafe_allow_html=True)

class VolumeProfileAnalyzer:
    def __init__(self, api_key=None, api_secret=None):
        """Inicializa o analisador"""
        if api_key and api_secret:
            self.client = Client(api_key, api_secret)
        else:
            self.client = Client()  # Cliente público (sem trading)
    
    def get_historical_data(self, symbol, interval, lookback_hours):
        """Busca dados históricos da Binance"""
        try:
            start_time = datetime.now() - timedelta(hours=lookback_hours)
            start_str = start_time.strftime("%d %b %Y %H:%M:%S")
            
            klines = self.client.get_historical_klines(
                symbol, 
                interval, 
                start_str
            )
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 
                'volume', 'close_time', 'quote_volume', 'trades',
                'taker_buy_base', 'taker_buy_quote', 'ignore'
            ])
            
            # Conversões
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['taker_buy_base'] = df['taker_buy_base'].astype(float)
            df['taker_sell_base'] = df['volume'] - df['taker_buy_base']
            
            return df
            
        except Exception as e:
            st.error(f"Erro ao buscar dados: {e}")
            return None
    
    def calculate_volume_profile(self, df, num_bins=50):
        """Calcula Volume Profile completo"""
        if df is None or len(df) == 0:
            return None
        
        price_min = df['low'].min()
        price_max = df['high'].max()
        
        # Cria bins de preço
        bins = np.linspace(price_min, price_max, num_bins + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2
        
        # Inicializa volumes
        total_volume = np.zeros(num_bins)
        buy_volume = np.zeros(num_bins)
        sell_volume = np.zeros(num_bins)
        
        # Distribui volume por bin
        for idx, row in df.iterrows():
            # Encontra bins que a vela toca
            mask = (bin_centers >= row['low']) & (bin_centers <= row['high'])
            num_bins_touched = np.sum(mask)
            
            if num_bins_touched > 0:
                vol_per_bin = row['volume'] / num_bins_touched
                buy_per_bin = row['taker_buy_base'] / num_bins_touched
                sell_per_bin = row['taker_sell_base'] / num_bins_touched
                
                total_volume[mask] += vol_per_bin
                buy_volume[mask] += buy_per_bin
                sell_volume[mask] += sell_per_bin
        
        # Cria DataFrame do profile
        profile_df = pd.DataFrame({
            'price': bin_centers,
            'total_volume': total_volume,
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'delta': buy_volume - sell_volume
        })
        
        # Remove bins sem volume
        profile_df = profile_df[profile_df['total_volume'] > 0]
        
        if len(profile_df) == 0:
            return None
        
        # POC (Point of Control)
        poc_idx = profile_df['total_volume'].idxmax()
        poc_price = profile_df.loc[poc_idx, 'price']
        poc_volume = profile_df.loc[poc_idx, 'total_volume']
        
        # Value Area (70% do volume)
        total_vol = profile_df['total_volume'].sum()
        value_area_vol = total_vol * 0.70
        
        # Ordena por volume para encontrar VA
        sorted_profile = profile_df.sort_values('total_volume', ascending=False)
        cumsum = 0
        value_area_prices = []
        
        for idx, row in sorted_profile.iterrows():
            cumsum += row['total_volume']
            value_area_prices.append(row['price'])
            if cumsum >= value_area_vol:
                break
        
        vah = max(value_area_prices)
        val = min(value_area_prices)
        
        # HVN (High Volume Nodes) - acima de 1 desvio padrão
        mean_vol = profile_df['total_volume'].mean()
        std_vol = profile_df['total_volume'].std()
        hvn_threshold = mean_vol + std_vol
        hvn = profile_df[profile_df['total_volume'] > hvn_threshold]['price'].tolist()
        
        # LVN (Low Volume Nodes) - abaixo de 1 desvio padrão
        lvn_threshold = mean_vol - std_vol
        lvn = profile_df[profile_df['total_volume'] < lvn_threshold]['price'].tolist()
        
        # Preço atual
        current_price = df['close'].iloc[-1]
        
        # Delta analysis
        total_delta = profile_df['delta'].sum()
        delta_at_poc = profile_df.loc[poc_idx, 'delta']
        
        return {
            'poc': poc_price,
            'poc_volume': poc_volume,
            'vah': vah,
            'val': val,
            'hvn': hvn,
            'lvn': lvn,
            'profile': profile_df,
            'current_price': current_price,
            'total_delta': total_delta,
            'delta_at_poc': delta_at_poc,
            'value_area_volume_pct': (cumsum / total_vol) * 100
        }
    
    def get_market_structure(self, vp_data):
        """Analisa estrutura de mercado baseada no VP"""
        if vp_data is None:
            return None
        
        current = vp_data['current_price']
        poc = vp_data['poc']
        vah = vp_data['vah']
        val = vp_data['val']
        
        # Posição relativa
        if current > vah:
            position = "ACIMA da Value Area"
            bias = "BULLISH 🟢"
            strategy = "Procure por pullbacks ao VAH para compra"
        elif current < val:
            position = "ABAIXO da Value Area"
            bias = "BEARISH 🔴"
            strategy = "Procure por rallys ao VAL para venda"
        else:
            position = "DENTRO da Value Area"
            bias = "NEUTRO 🟡"
            strategy = "Range-bound: opere entre VAL e VAH"
        
        # Distância ao POC
        distance_to_poc = ((current - poc) / poc) * 100
        
        # Alerta de reversão
        reversal_alert = None
        if abs(distance_to_poc) > 2:
            reversal_alert = f"⚠️ Preço {abs(distance_to_poc):.2f}% distante do POC - Possível retorno!"
        
        # Delta analysis
        delta_bias = "Neutro"
        if vp_data['total_delta'] > 0:
            delta_bias = "Comprador dominante 🟢"
        elif vp_data['total_delta'] < 0:
            delta_bias = "Vendedor dominante 🔴"
        
        return {
            'position': position,
            'bias': bias,
            'strategy': strategy,
            'distance_to_poc': distance_to_poc,
            'reversal_alert': reversal_alert,
            'delta_bias': delta_bias
        }
    
    def create_dashboard_chart(self, df, vp_data, symbol):
        """Cria gráfico principal do dashboard"""
        if df is None or vp_data is None:
            return None
        
        # Cria subplots
        fig = make_subplots(
            rows=2, cols=2,
            column_widths=[0.7, 0.3],
            row_heights=[0.7, 0.3],
            specs=[
                [{"type": "candlestick", "rowspan": 2}, {"type": "bar"}],
                [None, {"type": "bar"}]
            ],
            subplot_titles=(
                f'{symbol} - Price Action',
                'Volume Profile',
                'Delta Profile'
            ),
            vertical_spacing=0.03,
            horizontal_spacing=0.02
        )
        
        # Candlestick
        fig.add_trace(
            go.Candlestick(
                x=df['timestamp'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Price',
                increasing_line_color='#00ff00',
                decreasing_line_color='#ff0000'
            ),
            row=1, col=1
        )
        
        # Volume Profile (horizontal bars)
        fig.add_trace(
            go.Bar(
                y=vp_data['profile']['price'],
                x=vp_data['profile']['total_volume'],
                orientation='h',
                name='Total Volume',
                marker=dict(
                    color=vp_data['profile']['total_volume'],
                    colorscale='Blues',
                    showscale=False
                ),
                hovertemplate='Price: $%{y:.2f}<br>Volume: %{x:.0f}<extra></extra>'
            ),
            row=1, col=2
        )
        
        # Destaca POC
        fig.add_trace(
            go.Scatter(
                y=[vp_data['poc']],
                x=[vp_data['poc_volume']],
                mode='markers',
                name='POC',
                marker=dict(color='yellow', size=15, symbol='star'),
                showlegend=False
            ),
            row=1, col=2
        )
        
        # Delta Profile
        colors = ['green' if d > 0 else 'red' for d in vp_data['profile']['delta']]
        fig.add_trace(
            go.Bar(
                y=vp_data['profile']['price'],
                x=vp_data['profile']['delta'],
                orientation='h',
                name='Delta',
                marker=dict(color=colors),
                hovertemplate='Price: $%{y:.2f}<br>Delta: %{x:.0f}<extra></extra>'
            ),
            row=2, col=2
        )
        
        # Linhas POC, VAH, VAL no gráfico de preço
        fig.add_hline(
            y=vp_data['poc'], 
            line_dash="solid", 
            line_color="yellow", 
            line_width=3,
            annotation_text="POC",
            annotation_position="right",
            row=1, col=1
        )
        
        fig.add_hline(
            y=vp_data['vah'], 
            line_dash="dash", 
            line_color="green", 
            line_width=2,
            annotation_text="VAH",
            annotation_position="right",
            row=1, col=1
        )
        
        fig.add_hline(
            y=vp_data['val'], 
            line_dash="dash", 
            line_color="red", 
            line_width=2,
            annotation_text="VAL",
            annotation_position="right",
            row=1, col=1
        )
        
        # Destaca HVN
        for hvn_price in vp_data['hvn']:
            fig.add_hline(
                y=hvn_price,
                line_dash="dot",
                line_color="lightblue",
                line_width=1,
                opacity=0.5,
                row=1, col=1
            )
        
        # Destaca LVN
        for lvn_price in vp_data['lvn']:
            fig.add_hline(
                y=lvn_price,
                line_dash="dot",
                line_color="orange",
                line_width=1,
                opacity=0.5,
                row=1, col=1
            )
        
        # Layout
        fig.update_layout(
            title=dict(
                text=f"<b>{symbol} Volume Profile Analysis</b>",
                x=0.5,
                xanchor='center'
            ),
            height=900,
            showlegend=True,
            xaxis_rangeslider_visible=False,
            hovermode='x unified',
            template='plotly_dark',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        fig.update_xaxes(title_text="Time", row=1, col=1)
        fig.update_yaxes(title_text="Price (USDT)", row=1, col=1)
        fig.update_xaxes(title_text="Volume", row=1, col=2)
        fig.update_xaxes(title_text="Delta", row=2, col=2)
        
        return fig

# Interface Streamlit
def main():
    st.title("📊 Volume Profile Crypto Dashboard")
    st.markdown("**Desenvolvido para Daytrade - Integração com SMC/ICT**")
    
    # Sidebar - Configurações
    with st.sidebar:
        st.header("⚙️ Configurações")
        
        # API Keys (opcional)
        with st.expander("🔑 API Binance (Opcional)"):
            api_key = st.text_input("API Key", type="password", help="Deixe vazio para usar dados públicos")
            api_secret = st.text_input("API Secret", type="password")
        
        st.markdown("---")
        
        # Parâmetros de análise
        st.subheader("📈 Parâmetros")
        
        symbol = st.selectbox(
            "Par",
            ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", 
             "ADAUSDT", "DOGEUSDT", "MATICUSDT", "DOTUSDT", "AVAXUSDT"],
            index=0
        )
        
        interval = st.selectbox(
            "Timeframe",
            ["1m", "3m", "5m", "15m", "30m", "1h", "4h"],
            index=2,
            help="Recomendado: 5m para scalping, 15m para daytrade"
        )
        
        lookback_hours = st.slider(
            "Horas de Histórico",
            min_value=1,
            max_value=24,
            value=4,
            help="Período para calcular o Volume Profile"
        )
        
        num_bins = st.slider(
            "Níveis de Preço (Bins)",
            min_value=20,
            max_value=100,
            value=50,
            step=10,
            help="Mais níveis = mais precisão, mas mais lento"
        )
        
        st.markdown("---")
        
        auto_refresh = st.checkbox("🔄 Auto-refresh", value=False)
        if auto_refresh:
            refresh_rate = st.slider("Segundos", 10, 300, 30)
        
        st.markdown("---")
        
        analyze_button = st.button("🚀 ANALISAR", type="primary", use_container_width=True)
    
    # Inicializa analyzer
    if api_key and api_secret:
        analyzer = VolumeProfileAnalyzer(api_key, api_secret)
    else:
        analyzer = VolumeProfileAnalyzer()
    
    # Container principal
    if analyze_button or auto_refresh:
        with st.spinner("📡 Buscando dados da Binance..."):
            # Busca dados
            df = analyzer.get_historical_data(symbol, interval, lookback_hours)
            
            if df is not None and len(df) > 0:
                # Calcula Volume Profile
                vp_data = analyzer.calculate_volume_profile(df, num_bins)
                
                if vp_data is not None:
                    # Análise de estrutura
                    market_structure = analyzer.get_market_structure(vp_data)
                    
                    # Métricas principais
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            "💰 Preço Atual",
                            f"${vp_data['current_price']:.2f}",
                            delta=f"{market_structure['distance_to_poc']:+.2f}% do POC"
                        )
                    
                    with col2:
                        st.metric(
                            "🎯 POC",
                            f"${vp_data['poc']:.2f}",
                            delta=f"Vol: {vp_data['poc_volume']:.0f}"
                        )
                    
                    with col3:
                        st.metric(
                            "📈 VAH",
                            f"${vp_data['vah']:.2f}",
                            delta="Value Area High"
                        )
                    
                    with col4:
                        st.metric(
                            "📉 VAL",
                            f"${vp_data['val']:.2f}",
                            delta="Value Area Low"
                        )
                    
                    # Alertas
                    st.markdown("---")
                    
                    col_alert1, col_alert2 = st.columns(2)
                    
                    with col_alert1:
                        st.markdown(f"""
                        <div class="alert-box alert-{'success' if 'BULLISH' in market_structure['bias'] else 'danger' if 'BEARISH' in market_structure['bias'] else 'warning'}">
                            <b>📍 Posição:</b> {market_structure['position']}<br>
                            <b>🎯 Viés:</b> {market_structure['bias']}<br>
                            <b>💡 Estratégia:</b> {market_structure['strategy']}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    with col_alert2:
                        st.markdown(f"""
                        <div class="alert-box alert-{'success' if 'Comprador' in market_structure['delta_bias'] else 'danger' if 'Vendedor' in market_structure['delta_bias'] else 'warning'}">
                            <b>📊 Delta Analysis:</b> {market_structure['delta_bias']}<br>
                            <b>Σ Delta Total:</b> {vp_data['total_delta']:.2f}<br>
                            <b>Delta no POC:</b> {vp_data['delta_at_poc']:.2f}
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Alerta de reversão
                    if market_structure['reversal_alert']:
                        st.warning(market_structure['reversal_alert'])
                    
                    # Alertas HVN/LVN
                    if len(vp_data['hvn']) > 0:
                        nearest_hvn = min(vp_data['hvn'], key=lambda x: abs(x - vp_data['current_price']))
                        distance_hvn = abs(vp_data['current_price'] - nearest_hvn) / vp_data['current_price']
                        if distance_hvn < 0.01:  # Menos de 1%
                            st.info(f"🔵 **HVN PRÓXIMO:** ${nearest_hvn:.2f} - Área de alta liquidez, possível suporte/resistência forte!")
                    
                    if len(vp_data['lvn']) > 0:
                        nearest_lvn = min(vp_data['lvn'], key=lambda x: abs(x - vp_data['current_price']))
                        distance_lvn = abs(vp_data['current_price'] - nearest_lvn) / vp_data['current_price']
                        if distance_lvn < 0.01:  # Menos de 1%
                            st.warning(f"⚡ **LVN PRÓXIMO:** ${nearest_lvn:.2f} - Vazio de volume, movimento rápido esperado!")
                    
                    st.markdown("---")
                    
                    # Gráfico principal
                    fig = analyzer.create_dashboard_chart(df, vp_data, symbol)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    
                    # Tabela de dados
                    with st.expander("📋 Dados Detalhados do Volume Profile"):
                        st.dataframe(
                            vp_data['profile'].sort_values('total_volume', ascending=False).head(20),
                            use_container_width=True
                        )
                    
                    # Integração com SMC/ICT
                    st.markdown("---")
                    st.subheader("🎓 Integração com SMC/ICT")
                    
                    col_smc1, col_smc2 = st.columns(2)
                    
                    with col_smc1:
                        st.markdown("""
                        **✅ Confluências Poderosas:**
                        - POC + Order Block = Setup premium
                        - VAH/VAL + Fair Value Gap = Zonas de reação
                        - HVN = Áreas de liquidez (igual Pool de liquidez ICT)
                        - LVN = Imbalances (similar a FVG)
                        """)
                    
                    with col_smc2:
                        st.markdown("""
                        **🎯 Como Usar no Trade:**
                        1. Identifique Order Blocks no seu gráfico
                        2. Confirme com HVN do Volume Profile
                        3. Entre quando preço retorna ao POC + OB
                        4. Stop: além do LVN mais próximo
                        5. Target: próximo HVN ou VAH/VAL
                        """)
                    
                    # Footer
                    st.markdown("---")
                    st.caption(f"⏰ Última atualização: {datetime.now().strftime('%H:%M:%S')} | 📊 Desenvolvido para Daytrade")
                    
                else:
                    st.error("❌ Erro ao calcular Volume Profile")
            else:
                st.error("❌ Erro ao buscar dados da Binance")
        
        # Auto-refresh
        if auto_refresh:
            time.sleep(refresh_rate)
            st.rerun()
    
    else:
        # Tela inicial
        st.info("👈 Configure os parâmetros na barra lateral e clique em **ANALISAR**")
        
        st.markdown("""
        ### 📚 Como Usar Este Dashboard
        
        **Volume Profile é uma ferramenta poderosa que mostra:**
        - 🎯 **POC (Point of Control):** Preço com maior volume = área de maior aceitação
        - 📈 **VAH (Value Area High):** Limite superior da zona de valor (70% do volume)
        - 📉 **VAL (Value Area Low):** Limite inferior da zona de valor
        - 🔵 **HVN (High Volume Nodes):** Áreas de alta liquidez = suporte/resistência forte
        - 🟠 **LVN (Low Volume Nodes):** Vazios de volume = movimento rápido
        
        **Integração com SMC/ICT:**
        - Combine Volume Profile com seus Order Blocks
        - Use POC como confluência para entradas
        - HVN = Pools de Liquidez
        - LVN = Fair Value Gaps / Imbalances
        
        **Configurações Recomendadas:**
        - **Scalping:** 5m timeframe, 2-4 horas de histórico
        - **Daytrade:** 15m timeframe, 4-8 horas de histórico
        - **Swing Intraday:** 1h timeframe, 12-24 horas
        """)

if __name__ == "__main__":
    main()