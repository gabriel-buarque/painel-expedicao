import logging
import smtplib
import threading
import time
import traceback
from email.message import EmailMessage

import streamlit as st

from caminhos import ARQUIVO_LOG, garantir_pastas

# Um alerta do mesmo título no máximo a cada 15 minutos
INTERVALO_MINIMO_ALERTA = 15 * 60
TIMEOUT_SMTP = 15  # segundos

_ultimos_alertas = {}
_trava = threading.Lock()


def configurar_logs():
    """Registra erros graves em logs/app_errors.log sem parar a aplicação."""
    try:
        garantir_pastas()
        log_path = ARQUIVO_LOG

        logger = logging.getLogger()
        logger.setLevel(logging.ERROR)

        # Evita múltiplos handlers apontando para o mesmo arquivo (duplicaria mensagens)
        ja_existe = any(
            isinstance(h, logging.FileHandler) and getattr(h, "baseFilename", "") == str(log_path)
            for h in logger.handlers
        )
        if not ja_existe:
            handler = logging.FileHandler(log_path, encoding="utf-8")
            handler.setLevel(logging.ERROR)
            handler.setFormatter(
                logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
            )
            logger.addHandler(handler)
    except Exception:
        # Sem permissão de escrita no servidor? Segue sem log em arquivo.
        pass


def obter_config_alerta():
    try:
        return st.secrets.get("alertas", {})
    except Exception:
        return {}


def em_producao():
    try:
        return st.secrets.get("ambiente", {}).get("modo", "desenvolvimento") == "producao"
    except Exception:
        return False


def _pode_enviar(titulo):
    """True se este título ainda não foi alertado dentro da janela de tempo."""
    agora = time.time()
    with _trava:
        ultimo = _ultimos_alertas.get(titulo, 0)
        if agora - ultimo < INTERVALO_MINIMO_ALERTA:
            return False
        _ultimos_alertas[titulo] = agora
        return True


def notificar_admin(titulo, erro):
    """Grava no log e, em produção, envia e-mail — com limite e timeout."""
    detalhe = "".join(traceback.format_exception(type(erro), erro, erro.__traceback__))
    logging.error(f"{titulo}: {detalhe}")

    if not em_producao():
        # Só no terminal e no log. NUNCA st.toast aqui:
        # notificar_admin é chamado de dentro de funções @st.cache_data, e o
        # Streamlit grava os elementos visuais criados ali para reproduzi-los
        # quando o cache é reusado. Na reprodução o bloco de layout original
        # já não existe, e o app quebra com CacheReplayClosureError.
        print(f"\n--- ERRO EM BACKGROUND ---\n{detalhe}\n--------------------------\n")
        return

    # Anti-inundação: banco fora do ar geraria um e-mail por clique de cada usuário
    if not _pode_enviar(titulo):
        return

    cfg = obter_config_alerta()
    if not cfg.get("smtp_host") or not cfg.get("destinatario"):
        return

    try:
        msg = EmailMessage()
        msg["Subject"] = f"🚨 {titulo}"
        msg["From"] = cfg.get("remetente", cfg.get("smtp_user"))
        msg["To"] = cfg["destinatario"]
        msg.set_content(
            f"Ocorreu um erro no Painel de Expedição.\n\nDetalhes:\n{detalhe}"
        )

        with smtplib.SMTP_SSL(
            cfg["smtp_host"],
            int(cfg.get("smtp_port", 465)),
            timeout=TIMEOUT_SMTP,
        ) as smtp:
            smtp.login(cfg["smtp_user"], cfg["smtp_password"])
            smtp.send_message(msg)

    except smtplib.SMTPAuthenticationError as e:
        logging.error(f"Alerta não enviado — usuário/senha SMTP incorretos: {e}")
    except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, OSError) as e:
        logging.error(f"Alerta não enviado — servidor SMTP inacessível: {e}")
    except Exception as e:
        logging.error(f"Alerta não enviado — falha não identificada: {e}")