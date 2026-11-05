from pathlib import Path


# 1. Descobre qual é a pasta raiz do projeto automaticamente
RAIZ = Path(__file__).resolve().parent

# 2. Define onde ficam as subpastas
PASTA_ASSETS = RAIZ / "assets"
PASTA_DADOS_LOCAIS = RAIZ / "dados_locais"
PASTA_LOGS = RAIZ / "logs"

# 3. Define os caminhos exatos dos arquivos
ARQUIVO_LOG = PASTA_LOGS / "app_errors.log"
CACHE_DADOS = PASTA_DADOS_LOCAIS / "ultimo_df_banco.csv"
PLANILHA_METAS = PASTA_DADOS_LOCAIS / "Metas.xlsx"


LOGO_FUNDO_STR = str(PASTA_ASSETS / "Fundo logo Nassau.png")
LOGO_TRANSPARENTE_STR = str(PASTA_ASSETS / "Fundo-transp.png")

def garantir_pastas():
    """Cria as pastas automaticamente se alguém baixar o projeto sem elas"""
    PASTA_ASSETS.mkdir(exist_ok=True)
    PASTA_DADOS_LOCAIS.mkdir(exist_ok=True)
    PASTA_LOGS.mkdir(exist_ok=True)