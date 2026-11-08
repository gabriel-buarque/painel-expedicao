<div align = "center">

# **Sistema Corporativo para Monitoramento de Expedição de Cimento**



![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red?logo=streamlit)
![MariaDB](https://img.shields.io/badge/MariaDB-Database-blue?logo=mariadb)
![Status](https://img.shields.io/badge/Status-Em%20Produção-success)
![License](https://img.shields.io/badge/License-Private-lightgrey)
</div>
<br>
<br>

##  ***Objetivos do Projeto***
### O principal objetivo deste sistema é fornecer uma solução robusta e centralizada para o **acompanhamento em tempo real do processo de expedição** das unidades fabris (Itabira, Itapetinga e Itapicuru). 

### A plataforma foi desenvolvida para apoiar a tomada de decisão logística e comercial através dos seguintes pilares:

### **Monitoramento em Tempo Real:** Visualização instantânea do fluxo de expedição, permitindo a verificação em tempo real das filas de atendimento e do status de carregamento dos veículos.
### **Análise de Volume de Saídas:** Rastreamento preciso do volume físico (em sacos convertidos) e financeiro faturado, distribuído e detalhado por **tipo de cimento** (ex: CP II, CP III).
### **Segmentação de Clientes:** Inteligência de dados configurada para identificar o comportamento de saídas e performance de vendas de acordo com o **segmento de clientes** atendidos pela corporação.
### **Previsibilidade e Ritmo de Metas:** Confronto matemático diário entre o volume real faturado e as metas comerciais estipuladas para o período, indicando o desvio (atraso/adiantamento) e a média diária necessária para atingimento dos resultados.
### **Contingência Operacional (Modo Offline):** Garantia de disponibilidade contínua através de um sistema de sincronização e cache local, permitindo que a equipe consulte os relatórios e históricos mesmo em cenários de instabilidade no banco de dados principal.

<br>
<br>
<br>

# **1.  Visão Geral do Sistema**

### O Painel de Expedição Nassau é uma aplicação corporativa de alta performance desenvolvida sobre o ecossistema Python e a biblioteca Streamlit. O propósito central do sistema é monitorar, consolidar e auditar em tempo real o fluxo físico e financeiro de saída de cimento das unidades operacionais estratégicas (Itabira, Itapetinga, Itapicuru e Cibrasa).
### Como a expedição industrial funciona de forma ininterrupta, o sistema foi projetado para ser totalmente tolerante a falhas. Ele utiliza um modelo de contingência dinâmica ('Principal' e 'Clone') que, em caso de queda, recorre a um backup local em cache para manter a operação visível, enviando simultaneamente alertas de erro em background via e-mail seguro (SMTP).
<br>
<br>
<br>
<br>


# **2.  Arquitetura Modular e Estrutura de Arquivos**
<br>

### Para garantir a manutenibilidade, isolamento de escopo e clareza de desenvolvimento, o código fonte foi distribuído em módulos especializados. A tabela abaixo detalha a matriz de responsabilidade de cada componente:
<br>
<br>

| Componente | Função Estrutural | Responsabilidades Principais |
| :--- | :--- | :--- |
| `clone.py` | Ponto de Entrada (Produção) | Atua como interceptador global de erros. Tenta executar o fluxo principal e, em caso de falha fatal de infraestrutura, renderiza instantaneamente o ambiente de contingência isolado. |
| `main.py` | Ponto de Entrada (Desenvolvimento) | Gerencia o fluxo de execução principal do painel operacional, orquestrando a lógica de negócio, processamento temporal de competências e montagem de dashboards dinâmicos. |
| `dados.py` | Camada de Persistência e Dados | Centraliza as consultas SQL à base MariaDB, conexões físicas, leitura e normalização de planilhas comerciais (Excel), além da gestão de backups frios em formato CSV. |
| `interface.py` | Camada de Apresentação (UI) | Garante o isolamento dos componentes visuais. Constrói menus laterais interativos, barras de progresso comercial e renderiza os gráficos de progressão diária acumulada. |
| `alertas.py` | Subsistema de Telemetria e Logs | Controla a escrita de logs físicos do sistema (app_errors.log) e gerencia a formatação e despacho de alertas SMTP criptografados para a equipe de engenharia. |


<br>
<br>
<br>
<br>
<br>

# **3. O Mecanismo de Contingência de Alta Disponibilidade**

### A estabilidade contínua do painel é garantida pelo arquivo `clone.py`, que utiliza a biblioteca nativa runpy para orquestrar a execução segura do sistema. Esse mecanismo blinda a aplicação, garantindo que o usuário não sofra interrupções visuais ou operacionais em caso de oscilações de rede, falhas de banco de dados ou indisponibilidade de APIs.
<br>

## Fluxo de Interceptação de Erros (Passo a Passo) 
### 1- O servidor Streamlit inicializa a execução pelo arquivo mestre de produção: `clone.py`.


### 2- O bloco try invoca o script de processamento em tempo real: `runpy.run_path("main.py", run_name="_main_")`.


### 3- Se a infraestrutura de rede e os servidores estiverem normais, o painel roda sob o arquivo original carregando os dados do banco de dados relacional.


### 4- Caso ocorra qualquer exceção fatal (ex: queda de conexão de rede ou falha de handshake SQL), o bloco except intercepta a quebra, dispara a telemetria e limpa o buffer visual do usuário com o método `st.empty()`.


### 5- O ambiente entra automaticamente em Modo Clone Isolado, mantendo as exibições visuais estáveis, porém alimentado pelo último arquivo de cache válido (`ultimo_df_banco.csv`).

#### OBS: O modo clone roda de forma autônoma e autocontida. Ele não importa os módulos `dados.py` ou `interface.py` externos para mitigar qualquer risco de efeito cascata originado por arquivos de código corrompidos.
<br>
<br>
<br>
<br>


# **4. Camada de Dados, Regras de Negócio e Gestão de Cache**

### O módulo de dados realiza um tratamento analítico refinado das saídas de expedição. Um dos pilares é a aplicação automática das Regras Comerciais de Conversão de Peso, visto que o cimento faturado em sacos fora do padrão industrial precisa ser normalizado para a unidade padrão de 50 kg para fins de contabilização e acompanhamento fiel de metas:
<br>


```python
# Expressão matemática de normalização aplicada via Numpy
df_maria["Quantidade (Sacos)"] = np.where(
    df_maria["Item"].str.contains("42,5|42.5"),
    df_maria["Quantidade_Bruta"] * 0.85, # Proporção (42.5kg / 50kg)
    np.where(
        df_maria["Item"].str.contains("40"),
        df_maria["Quantidade_Bruta"] * 0.80, # Proporção (40kg / 50kg)
        df_maria["Quantidade_Bruta"] # Peso já padrão de 50kg
    )
)
```


## Estratégia Avançada de Otimização de Performance
### Para evitar gargalos de performance e requisições excessivas que degradem a infraestrutura do banco de dados corporativo, o sistema distribui o ciclo de vida da informação através de duas diretrizes de cache tático:

### `st.cache_resource` (TTL Infinito): Aplicado à função conectar_mariadb(). Garante que o pool de conexão de rede seja estabelecido uma única vez e reaproveitado por todas as sessões e atualizações de página de usuários ativos.

### `st.cache_data` (TTL Controlado): Aplicado à planilha comercial de metas (TTL de 10 minutos / 600 segundos) e às volumetrias brutas de notas fiscais emitidas (TTL de 5 minutos / 300 segundos).
<br>
<br>

## Customização do Feedback Visual (Spinners Informativos)

### Para elevar o nível de experiência do usuário (UX), a documentação normatiza o uso do parâmetro show_spinner em todas as chamadas de processamento em background. Isso substitui mensagens puras em código por instruções claras em português:
```python
@st.cache_data(ttl=300, show_spinner="Baixando e processando notas fiscais. Isso pode levar alguns segundos...")
def carregar_dados_sistema():
    # Bloco lógico de extração da query SQL ...
```
<br>
<br>
<br>
<br>


# **5. Subsistema de Telemetria e Alertas Automatizados**
### O tratamento de falhas opera de forma modular e inteligente. O arquivo alertas.py atua em conjunto com as variáveis de ambiente protegidas em `st.secrets` para garantir o isolamento entre os ciclos de teste e a operação real de produção.

### A função de notificação avalia a chave `st.secrets["ambiente"]["modo"]`. Se o app estiver em modo de desenvolvimento local, nenhuma notificação por e-mail é disparada, evitando o congestionamento da caixa de entrada da equipe de manutenção. O erro é detalhado no console do terminal de depuração e um pop-up temporário e discreto é gerado no canto da tela através do comando `st.toast()`.

### Em modo de produção, o sistema conecta-se ao servidor SMTP via protocolo seguro SSL (porta padrão 465) e encapsula o rastro de pilha completo do erro (gerado por `traceback.format_exception`) no corpo de uma mensagem estruturada via EmailMessage, garantindo respostas rápidas de manutenção.
<br>
<br>
<br>
<br>

# **6. Guia Prático de Implantação e Deploy**
### Para o correto funcionamento do ambiente resiliente, a infraestrutura deve seguir rigorosamente as rotinas de inicialização documentadas abaixo:

| Ambiente de Execução | Comando de Inicialização | Comportamento Esperado |
| :--- | :--- | :--- |
| *Desenvolvimento Local* | `streamlit run main.py` | Dispara o painel em modo transparente. Falhas críticas gerarão a tela vermelha nativa do Streamlit, expondo linhas e variáveis exatas para correção rápida. |
| *Produção Corporativa* | `streamlit run clone.py` | Ativa a malha de resiliência. O usuário final nunca visualizará mensagens de erro. Em caso de quedas de BD, o painel exibirá os dados offline do backup estável. |

<br>
<br>
<br>
<br>

# **7. Gerenciamento de Estado e Persistência Visual**
### Para evitar que o painel "esqueça" as escolhas do usuário a cada recarregamento de página (comportamento padrão do Streamlit), o módulo `interface.py` utiliza o dicionário global `st.session_state`.

### Regras de Estado Implementadas:

### Memória de Página: A variável  `st.session_state.pagina_atual`  garante que, ao clicar em "Painel Geral" ou em uma fábrica específica ("ITABIRA", "ITAPETINGA", etc.), o painel preserve a aba ativa mesmo após as atualizações de banco de dados (que ocorrem a cada 5 minutos).

### Controle de Meses (Checkbox): O estado de cada mês (ex: `st.session_state["mes_6"]`) é salvo individualmente. O sistema possui uma trava de segurança que impede a tela de "quebrar" caso o usuário desmarque todos os meses: se a lista ficar vazia, o sistema força o mês de Junho (6) como padrão para manter o aplicativo funcional.

### Master Checkbox: O botão "Selecionar Todos os Meses" aplica um broadcast de estado verdadeiro/falso para todos os meses simultaneamente via função de callback (`on_change=alterar_todos_meses`).
<br>
<br>
<br>
<br>


# **8. Resiliência de Caminhos de Arquivos Locais (Pathlib)**
### O sistema lida com leitura e escrita de arquivos físicos (como o app_errors.log, o backup `ultimo_df_banco.csv` e a planilha Metas.xlsx). Para evitar falhas de caminho (o famoso erro File Not Found) ao rodar a aplicação em diferentes servidores ou pastas, o código utiliza a biblioteca pathlib.

## Estratégia de Busca (Fallback de Diretório):
### Os arquivos `dados.py` e `clone.py` procuram pelos arquivos locais em duas camadas:

### Primeiro procuram na mesma pasta do script em execução `(Path(__file__).resolve().parent)`.

### Se não encontrarem, recuam e procuram na pasta raiz do projeto `(Path(...).parent.parent)`.
### Isso garante que o sistema de contingência funcione mesmo que o arquivo `clone.py` seja executado a partir de um subdiretório.
<br>
<br>
<br>
<br>

# **9. Fluxo de Atualização Operacional (O Arquivo de Metas)**

### Formatação Obrigatória: As colunas devem se chamar rigorosamente "Unidade", "Mês", "Vendas" e "Dias".

### Regra de Nomenclatura: As abas e os nomes das fábricas não devem conter caracteres especiais que diferem do padrão (ex: usar "ITABIRA" em vez de "Fábrica Itabira").

### Tempo de Propagação: Devido ao comando `@st.cache_data(ttl=600)`, o usuário deve ser instruído de que novas metas inseridas no Excel podem levar até 10 minutos para refletirem no painel web.
<br>
<br>
<br>
<br>


# **10. O Schema Anti-Falhas e Isolamento do Clone (SPOF)**
### O arquivo `clone.py` atua como o "Bote Salva-Vidas" da aplicação e possui um schema de log totalmente autossuficiente (`_configurar_log_clone`)

### *Desacoplamento de Emergência*: O clone não importa o arquivo `alertas.py`. Se o sistema cair por causa de um erro de sintaxe justamente no módulo de alertas, o clone sobreviverá porque possui seu próprio motor de registro.

### *Garantia de Rastreabilidade*: A primeira ação do bloco de exceção é gravar o rastro da falha no disco físico (`app_errors.log`). O aviso por e-mail é secundário. Isso garante que a prova do erro sempre ficará salva no servidor, mesmo se a rede de internet cair no momento do crash.
<br>
<br>
<br>
<br>

# **11. Zonas Críticas e Invioláveis**
### O sistema possui pilares lógicos que garantem a contingência. A alteração indevida dos blocos abaixo comprometerá a estabilidade da aplicação:

### **O Comando `st.empty()`**: Localizado no bloco de exceção do `clone.py`. Nunca deve ser removido. Ele funciona como um "apagador", limpando a interface corrompida do `main.py` antes de desenhar o painel de contingência offline.

### **Cache de Banco de Dados**: A função `conectar_mariadb()` utiliza obrigatoriamente `@st.cache_resource`. Alterar para `cache_data` fará o sistema tentar clonar a conexão TCP/IP para cada usuário, esgotando o limite do MariaDB rapidamente .

### **Fallback de Meses Vazios**: Na barra lateral (`interface.py`), existe uma trava que força a seleção do mês "6" (Junho) caso o usuário desmarque todos os botões. Isso impede o Pandas de gerar erros matemáticos de divisão por zero.
<br>
<br>
<br>
<br>


# **12. Dependências e Configuração de Ambiente (Secrets)**
### Para que qualquer pessoa consiga realizar o deploy da aplicação do zero, é necessário garantir que as bibliotecas corretas estejam instaladas.

### Bibliotecas Python Exigidas (requirements.txt):
| Biblioteca | Propósito no Sistema |
| :--- | :--- |
| `streamlit` | Framework principal de renderização web e interface. |
|`pandas` | Manipulação e limpeza de dados (DataFrames). |
| `numpy` | Motor de cálculo temporal (dias úteis) e condicional (Run Rate). |
| `mysql-connector-python` | Driver puro para MariaDB (contorna a lentidão do SQLAlchemy). |
| `openpyxl` | Motor de leitura do arquivo de metas comercial (.xlsx). |



