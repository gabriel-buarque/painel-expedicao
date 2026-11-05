from caminhos import LOGO_TRANSPARENTE_STR
import streamlit as st
import pandas as pd
import numpy as np
from alertas import notificar_admin
from datetime import datetime


def renderizar_sidebar(mapa_meses):
    """
    Cria a barra lateral (menu) onde o usuário escolhe meses e fábricas.
    """
    # Se for o primeiro acesso da sessão, define a página padrão como Painel Geral
    if "pagina_atual" not in st.session_state:
        st.session_state.pagina_atual = "Painel Geral"

  
    mes_padrao = datetime.now().month


    # Configura a memória da barra lateral para iniciar com Julho marcado
    for num_mes in mapa_meses.values():
        if f"mes_{num_mes}" not in st.session_state:
            st.session_state[f"mes_{num_mes}"] = (num_mes == mes_padrao)

    # Inicia a construção visual da barra esquerda escura
    with st.sidebar:
        
        st.image(LOGO_TRANSPARENTE_STR, width=110)
        st.title("Controle de Expedição")
        st.markdown("---")

            # botao de atualizar dados
        if st.button(":material/sync: Atualizar dados", use_container_width=True,
                     disabled=st.session_state.get("_atualizando", False)):
            st.session_state["_atualizando"] = True

            # Só o cache de dados. A conexão (cache_resource) continua viva.
            st.cache_data.clear()

            # Volta os filtros ao padrão SEM destruir os widgets
            for n_m in mapa_meses.values():
                st.session_state[f"mes_{n_m}"] = (n_m == mes_padrao)
            st.session_state["check_todos"] = False
            st.session_state.pagina_atual = "Painel Geral"

            st.session_state["_atualizando"] = False
            st.toast("Dados atualizados", icon=":material/check_circle:")
            st.rerun()

        st.markdown("---")
        st.markdown("**:material/date_range: Competência temporal**")
        
        meses_selecionados = []
        
        # Caixa expansível com os 12 meses do ano comercial
        with st.expander(str(datetime.now().year), expanded=True):
            
            # Caixa mestre: Marcar tudo / Desmarcar tudo
            def alterar_todos_meses():
                estado = st.session_state["check_todos"]
                for n_m in mapa_meses.values():
                    st.session_state[f"mes_{n_m}"] = estado

            st.checkbox("Selecionar Todos os Meses", key="check_todos", on_change=alterar_todos_meses)
            st.markdown("---")
            
            # Monta os checkboxes na tela e puxa se ele deve começar ativo ou inativo
            for nome, num in mapa_meses.items():
                if st.checkbox(nome, key=f"mes_{num}"):
                    meses_selecionados.append(num)
                
     
        # Se nenhum mês estiver marcado, mostra o aviso e congela a tela
        if not meses_selecionados:
            st.warning(":material/error_outline: Selecione pelo menos um mês.")
            st.stop()
        
        st.markdown("---")
        st.markdown("Escolha a tela que deseja visualizar:")
        
        # Controle de rotas das telas (Painel Geral)
        if st.button("Painel Geral", icon=":material/space_dashboard:", use_container_width=True):
            st.session_state.pagina_atual = "Painel Geral"
            
        st.markdown("---")
        st.markdown("**:material/domain: Unidades**")
        
        # Botões das fábricas da corporação
        for fabrica in ["ITABIRA", "ITAPETINGA", "ITAPICURU", "CIBRASA"]:
            if st.button(fabrica, use_container_width=True):
                st.session_state.pagina_atual = fabrica

        st.markdown("---")
        st.caption("Controle de Expedição · Cimento Nassau")
    
    # Retorna as variáveis organizadas de volta para o motor principal (main.py)
    return sorted(list(set(meses_selecionados))), st.session_state.pagina_atual
