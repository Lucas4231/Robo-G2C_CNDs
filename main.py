import os
import json
import re
import time
import requests
from datetime import datetime

BASE_URL = "https://g2ccontabilidade.app.questorpublico.com.br"  
TOKEN = "2be9472b4669f32f8efe24a4730ca906"                       
DESTINO_BASE = r"C:\Users\RH 05\Desktop\CNDs"
CNPJS_PATH = "cnpjs.txt"
REGISTRO_PATH = "baixados.json"

# Pausas (segundos)
REQUEST_SLEEP = 0.6      
DOWNLOAD_SLEEP = 1.5     
BETWEEN_CNPJ_SLEEP = 3   


def safe_str(value):
    """
    Garante que o valor seja uma string segura para uso em nomes de arquivos/pastas
    e remove caracteres proibidos no Windows: \\ / : * ? " < > |
    """
    if value is None:
        return "Desconhecido"
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return re.sub(r'[\\/:*?"<>|]', "_", value)

def carregar_cnpjs():
    """Carrega a lista de CNPJs do arquivo de texto (um por linha)."""
    if not os.path.exists(CNPJS_PATH):
        print(f"❌ Arquivo {CNPJS_PATH} não encontrado.")
        return []
    with open(CNPJS_PATH, "r", encoding="utf-8") as f:
        cnpjs = [linha.strip() for linha in f if linha.strip()]
    print(f"📄 {len(cnpjs)} CNPJ(s) carregado(s) de {CNPJS_PATH}")
    return cnpjs

def carregar_registro():
    """Carrega o registro (dict) de arquivos já baixados. Se não existir, retorna dict vazio."""
    if not os.path.exists(REGISTRO_PATH):
        return {}
    try:
        with open(REGISTRO_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
            if isinstance(data, list):
                return {item: {} for item in data}
    except Exception as e:
        print(f"⚠️ Erro ao ler {REGISTRO_PATH}: {e} — iniciando registro vazio.")
    return {}


def salvar_registro(registro):
    """Salva o registro (dict) de arquivos baixados."""
    try:
        with open(REGISTRO_PATH, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ Não foi possível salvar {REGISTRO_PATH}: {e}")


def buscar_certidoes(cnpj, mes, ano):
    """
    Consulta as certidões disponíveis para um CNPJ, mês e ano.
    Retorna lista de certificados (cada um é dict) ou lista vazia.
    """
    endpoint = f"{BASE_URL}/api/v1/{TOKEN}/pegarcertidoesmesanocnpj"
    payload = {
        "Cnpj": [cnpj],
        "Month": str(mes).zfill(2),
        "Year": str(ano),
        "PageNumber": 1
    }
    try:
        resp = requests.post(endpoint, json=payload, timeout=30)
        if resp.status_code == 200:
            dados = resp.json()
            certificados = dados.get("certificates", []) if isinstance(dados, dict) else []
            if certificados:
                print(f"📌 {cnpj} ({mes:02d}/{ano}) -> {len(certificados)} item(s) encontrados")
            else:
            
                pass
            return certificados
        else:
            print(f"❌ Erro {resp.status_code} ao buscar certidões de {cnpj} ({mes:02d}/{ano})")
            return []
    except requests.RequestException as e:
        print(f"⚠️ Erro de conexão ao buscar certidões de {cnpj} ({mes:02d}/{ano}): {e}")
        return []
    except Exception as e:
        print(f"⚠️ Erro inesperado ao buscar certidões de {cnpj}: {e}")
        return []


def baixar_arquivo(file_id, caminho_destino):
    """
    Baixa o arquivo pela API usando file_id e salva em caminho_destino.
    Retorna True se baixou com sucesso, False caso contrário.
    """
    if not file_id:
        print("⚠️ file_id inválido - pulando download.")
        return False

    endpoint = f"{BASE_URL}/api/v1/{TOKEN}/pegararquivo?fileId={file_id}"
    try:
        resp = requests.post(endpoint, timeout=60)
        if resp.status_code == 200 and resp.content:
            # salva o conteúdo binário
            with open(caminho_destino, "wb") as f:
                f.write(resp.content)
            return True
        else:
            print(f"❌ Falha ao baixar {file_id} (status {resp.status_code})")
            return False
    except requests.RequestException as e:
        print(f"⚠️ Erro de rede ao baixar {file_id}: {e}")
        return False
    except Exception as e:
        print(f"⚠️ Erro inesperado ao baixar {file_id}: {e}")
        return False


def listar_todas_certidoes():
    cnpjs = carregar_cnpjs()
    if not cnpjs:
        return

    registro = carregar_registro()  # dict: { fileid: {meta} }
    novos_baixados = 0
    ja_existentes = 0

    ano_atual = datetime.now().year
    anos = [ano_atual - 1, ano_atual]
    meses = range(1, 13)

    for idx, cnpj in enumerate(cnpjs, start=1):
        print(f"\n🔍 [{idx}/{len(cnpjs)}] Iniciando varredura para CNPJ: {cnpj}")
        encontrou_algum_para_cnpj = False

        for ano in anos:
            for mes in meses:
                certificados = buscar_certidoes(cnpj, mes, ano)

                # pausa entre buscas para não sobrecarregar
                time.sleep(REQUEST_SLEEP)

                if not certificados:
                    # opcional: print para meses sem resultado
                    # print(f"✅ {cnpj} ({mes:02d}/{ano}) -> Nenhuma certidão encontrada")
                    continue

                encontrou_algum_para_cnpj = True

                for cert in certificados:
                    # valores brutos
                    file_id_raw = cert.get("Filename") or cert.get("filename") or cert.get("FileName")
                    # se não tiver id do arquivo, ignoramos (não tem como baixar)
                    if not file_id_raw:
                        print("⚠️ Certidão sem Filename (não será baixada).")
                        continue

                    # sanitiza nomes para pastas e nome do arquivo (mas NÃO altera file_id_raw usado na API)
                    empresa_raw = cert.get("ClientContactName") or cert.get("ClientContactFederalRegistration") or cnpj
                    owner_raw = cert.get("CategoryOwnerDescription") or cert.get("CategoryDescription") or "Outros"
                    category_raw = cert.get("CategoryDescription") or "SemCategoria"

                    empresa = safe_str(empresa_raw)
                    owner = safe_str(owner_raw)
                    category = safe_str(category_raw)
                    file_id = str(file_id_raw).strip()

                    # nome do arquivo local (inclui file_id para garantir unicidade)
                    nome_arquivo = f"{category}_{ano}_{mes:02d}_{file_id}.pdf"
                    nome_arquivo = safe_str(nome_arquivo)

                    # se já baixado, pula
                    if file_id in registro:
                        print(f"⏩ {empresa} | {category} | {file_id} -> já baixado anteriormente.")
                        ja_existentes += 1
                        continue

                    # monta pastas com segurança (componentes já sanitizados)
                    pasta_empresa = os.path.join(DESTINO_BASE, empresa)
                    pasta_owner = os.path.join(pasta_empresa, owner)
                    pasta_categoria = os.path.join(pasta_owner, category)

                    # cria pastas recursivamente (seguro)
                    try:
                        os.makedirs(pasta_categoria, exist_ok=True)
                    except Exception as e:
                        print(f"⚠️ Não foi possível criar pasta {pasta_categoria}: {e}")
                        continue

                    caminho_final = os.path.join(pasta_categoria, nome_arquivo)

                    print(f"⬇️ Baixando: {empresa} | {owner} / {category} | fileId: {file_id}")
                    sucesso = baixar_arquivo(file_id, caminho_final)

                    # pausa entre downloads
                    time.sleep(DOWNLOAD_SLEEP)

                    if sucesso:
                        # registra o download (metadata útil)
                        registro[file_id] = {
                            "cnpj": cnpj,
                            "empresa": empresa,
                            "owner": owner,
                            "category": category,
                            "arquivo": caminho_final,
                            "data_download": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        salvar_registro(registro)
                        novos_baixados += 1
                        print(f"✅ Salvo em: {caminho_final}")
                    else:
                        print(f"❌ Falha ao baixar fileId {file_id}")

        if not encontrou_algum_para_cnpj:
            print(f"✅ Nenhuma certidão encontrada para o CNPJ {cnpj} em 2024-2025.")

        # pausa entre CNPJs para reduzir risco de bloqueio
        time.sleep(BETWEEN_CNPJ_SLEEP)

    # resumo final
    print("\n--- Resumo ---")
    print(f"Novos arquivos baixados: {novos_baixados}")
    print(f"Arquivos já existentes (pulados): {ja_existentes}")
    print(f"Total registros em {REGISTRO_PATH}: {len(registro)}")
    print("🏁 Varredura concluída!")


# ========== Execução ==========

if __name__ == "__main__":
    print(f"\n🚀 Iniciando varredura em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    listar_todas_certidoes()
