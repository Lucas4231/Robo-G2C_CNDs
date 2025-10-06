import os
import time
import requests
import json
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

API_URL = os.getenv("API_URL")
API_TOKEN = os.getenv("API_TOKEN")

def buscar_certidoes(cnpj, mes, ano):
    """Consulta as certidões no endpoint da API."""
    url = f"https://g2ccontabilidade.app.questorpublico.com.br/api/v1/2be9472b4669f32f8efe24a4730ca906/pegarcertidoesmesanocnpj"
    payload = {
        "Cnpj": [cnpj],
        "Month": str(mes),
        "Year": str(ano),
        "PageNumber": 1
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.get(url, headers=headers, json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"⚠️ Erro {response.status_code} ao buscar {cnpj} ({mes}/{ano})")
            return None
    except Exception as e:
        print(f"❌ Erro na requisição: {e}")
        return None


def listar_todas_certidoes():
    """Percorre todos os CNPJs, meses e anos definidos e mostra as certidões encontradas."""
    caminho_cnpjs = "cnpjs.txt"

    if not os.path.exists(caminho_cnpjs):
        print(f"❌ Arquivo '{caminho_cnpjs}' não encontrado!")
        print("💡 Dica: coloque o arquivo cnpjs.txt na mesma pasta do main.py, com um CNPJ por linha.")
        return

    with open(caminho_cnpjs, "r", encoding="utf-8") as f:
        cnpjs = [linha.strip() for linha in f if linha.strip()]

    print(f"📄 {len(cnpjs)} CNPJ(s) carregados do arquivo '{caminho_cnpjs}'.")

    anos = range(2023, 2026)
    meses = range(1, 13)

    for cnpj in cnpjs:
        print(f"\n🔎 Buscando histórico de certidões para {cnpj}...")

        for ano in anos:
            for mes in meses:
                resultados = buscar_certidoes(cnpj, mes, ano)

                # Pausa entre as requisições (0.5s)
                time.sleep(0.5)

                if not resultados:
                    continue

                certificates = resultados.get("certificates", [])
                if not certificates:
                    print(f"📌 {cnpj} ({mes}/{ano}) -> ✅ Nenhuma certidão encontrada")
                    continue

                print(f"📌 {cnpj} ({mes}/{ano}) -> {len(certificates)} CND(s) encontradas:")

                for cert in certificates:
                    nome_empresa = cert.get("ClientContactName", "Desconhecido")
                    categoria = cert.get("CategoryDescription", "Sem descrição")
                    origem = cert.get("CategoryOwnerDescription", "N/D")
                    emissao = cert.get("Dateemission", "N/D")
                    validade = cert.get("Dateexpiration", "N/D")
                    filename = cert.get("Filename", "N/D")

                    print(f"   - {nome_empresa} | {origem} ({categoria})")
                    print(f"     📅 Emissão: {emissao} | Validade: {validade}")
                    print(f"     🗂️ Filename: {filename}\n")


if __name__ == "__main__":
    listar_todas_certidoes()
