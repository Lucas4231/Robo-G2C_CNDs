import os
import json
import re
import time
import requests
from datetime import datetime

# ===================== CONFIGURAÇÕES =====================
BASE_URL = "https://g2ccontabilidade.app.questorpublico.com.br"
TOKEN = "2be9472b4669f32f8efe24a4730ca906"
DESTINO_BASE = r"C:\Users\RH 05\Desktop\CNDs"
CNPJS_PATH = "cnpjs.txt"
REGISTRO_PATH = "baixados.json"

REQUEST_SLEEP = 0.6
DOWNLOAD_SLEEP = 1.5
BETWEEN_CNPJ_SLEEP = 3
# =========================================================


# ========== Funções auxiliares ==========

def safe_str(value):
    if value is None:
        return "Desconhecido"
    if not isinstance(value, str):
        value = str(value)
    value = value.strip()
    value = re.sub(r"\s+", " ", value)
    return re.sub(r'[\\/:*?"<>|]', "_", value)


def carregar_cnpjs():
    if not os.path.exists(CNPJS_PATH):
        return []
    with open(CNPJS_PATH, "r", encoding="utf-8") as f:
        return [linha.strip() for linha in f if linha.strip()]


def salvar_cnpjs(cnpjs):
    try:
        with open(CNPJS_PATH, "w", encoding="utf-8") as f:
            for cnpj in sorted(set(cnpjs)):
                f.write(cnpj + "\n")
        print(f"💾 Lista de CNPJs atualizada ({len(cnpjs)} empresas).")
    except Exception as e:
        print(f"⚠️ Erro ao salvar {CNPJS_PATH}: {e}")


def carregar_registro():
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
        print(f"⚠️ Erro ao ler {REGISTRO_PATH}: {e}")
    return {}


def salvar_registro(registro):
    try:
        with open(REGISTRO_PATH, "w", encoding="utf-8") as f:
            json.dump(registro, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"⚠️ Não foi possível salvar {REGISTRO_PATH}: {e}")


# ========== Nova integração: Buscar Contatos ==========

def atualizar_cnpjs_com_api():
    """
    Faz um POST na API buscarcontatos e atualiza o arquivo cnpjs.txt
    - Adiciona novos CNPJs ativos
    - Remove CNPJs inativos
    """
    endpoint = f"{BASE_URL}/api/v1/{TOKEN}/buscarcontatos"

    print("\n🔄 Atualizando lista de CNPJs a partir da API Questor...")

    try:
        resp = requests.post(endpoint, timeout=30)
        if resp.status_code != 200:
            print(f"❌ Erro {resp.status_code} ao buscar contatos.")
            return

        dados = resp.json()
        contatos = dados.get("contatos", [])
        if not contatos:
            print("⚠️ Nenhum contato retornado pela API.")
            return

        # separa ativos e inativos
        ativos = {
            c["InscricaoFederal"].strip()
            for c in contatos
            if c.get("Tipo") == "Empresa/Cliente"
            and c.get("Status") == "Ativo"
            and c.get("InscricaoFederal")
        }
        inativos = {
            c["InscricaoFederal"].strip()
            for c in contatos
            if c.get("Tipo") == "Empresa/Cliente"
            and c.get("Status") == "Inativo"
            and c.get("InscricaoFederal")
        }

        cnpjs_atuais = set(carregar_cnpjs())

        novos = ativos - cnpjs_atuais
        removidos = cnpjs_atuais & inativos

        if novos:
            print(f"➕ {len(novos)} novos CNPJs adicionados.")
        if removidos:
            print(f"➖ {len(removidos)} CNPJs inativos removidos.")

        # atualiza a lista
        cnpjs_atualizados = (cnpjs_atuais | ativos) - inativos
        salvar_cnpjs(cnpjs_atualizados)

    except requests.RequestException as e:
        print(f"⚠️ Erro de conexão com a API: {e}")
    except Exception as e:
        print(f"⚠️ Erro inesperado ao atualizar CNPJs: {e}")


# ========== Comunicação com API de certidões ==========

def buscar_certidoes(cnpj, mes, ano):
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
            return certificados
        else:
            print(f"❌ Erro {resp.status_code} ao buscar certidões de {cnpj}")
            return []
    except requests.RequestException as e:
        print(f"⚠️ Erro de conexão ao buscar certidões: {e}")
        return []
    except Exception as e:
        print(f"⚠️ Erro inesperado ao buscar certidões de {cnpj}: {e}")
        return []


def baixar_arquivo(file_id, caminho_destino):
    if not file_id:
        return False
    endpoint = f"{BASE_URL}/api/v1/{TOKEN}/pegararquivo?fileId={file_id}"
    try:
        resp = requests.post(endpoint, timeout=60)
        if resp.status_code == 200 and resp.content:
            with open(caminho_destino, "wb") as f:
                f.write(resp.content)
            return True
        else:
            print(f"❌ Falha ao baixar {file_id} (status {resp.status_code})")
            return False
    except requests.RequestException as e:
        print(f"⚠️ Erro de rede ao baixar {file_id}: {e}")
        return False


# ========== Função principal ==========

def listar_todas_certidoes():
    atualizar_cnpjs_com_api()  # <-- integração chamada aqui
    cnpjs = carregar_cnpjs()
    if not cnpjs:
        print("❌ Nenhum CNPJ disponível após atualização.")
        return

    registro = carregar_registro()
    novos_baixados = 0
    ja_existentes = 0

    anos = [2024, 2025]
    meses = range(1, 13)

    for idx, cnpj in enumerate(cnpjs, start=1):
        print(f"\n🔍 [{idx}/{len(cnpjs)}] Iniciando varredura para CNPJ: {cnpj}")
        encontrou = False

        for ano in anos:
            for mes in meses:
                certificados = buscar_certidoes(cnpj, mes, ano)
                time.sleep(REQUEST_SLEEP)
                if not certificados:
                    continue

                encontrou = True
                for cert in certificados:
                    file_id = cert.get("Filename") or cert.get("filename") or cert.get("FileName")
                    if not file_id:
                        continue

                    empresa_raw = cert.get("ClientContactName") or cnpj
                    owner_raw = cert.get("CategoryOwnerDescription") or "Outros"
                    category_raw = cert.get("CategoryDescription") or "SemCategoria"

                    empresa = safe_str(empresa_raw)
                    owner = safe_str(owner_raw)
                    category = safe_str(category_raw)
                    file_id = str(file_id).strip()

                    nome_arquivo = safe_str(f"{category}_{ano}_{mes:02d}_{file_id}.pdf")

                    if file_id in registro:
                        ja_existentes += 1
                        continue

                    pasta_final = os.path.join(DESTINO_BASE, empresa, owner, category)
                    os.makedirs(pasta_final, exist_ok=True)
                    caminho_final = os.path.join(pasta_final, nome_arquivo)

                    print(f"⬇️ Baixando: {empresa} | {category} | {file_id}")
                    if baixar_arquivo(file_id, caminho_final):
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
                        print(f"❌ Falha ao baixar {file_id}")
                    time.sleep(DOWNLOAD_SLEEP)

        if not encontrou:
            print(f"✅ Nenhuma certidão encontrada para {cnpj}.")
        time.sleep(BETWEEN_CNPJ_SLEEP)

    print("\n--- Resumo ---")
    print(f"Novos arquivos baixados: {novos_baixados}")
    print(f"Arquivos já existentes: {ja_existentes}")
    print(f"Total em registro: {len(registro)}")
    print("🏁 Varredura concluída!")


# ========== Execução ==========

if __name__ == "__main__":
    print(f"\n🚀 Iniciando varredura em {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    listar_todas_certidoes()
