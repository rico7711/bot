from flask import Flask, render_template, request, jsonify, Response
import requests
import time
import json

app = Flask(__name__)

API_URL = "https://vps2.femmeestilo.com//message/sendText/ATENTOS"
API_KEY = "141525"

# Variáveis globais de controle
em_execucao = False
pausado = False

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/controle", methods=["POST"])
def controle():
    global em_execucao, pausado
    acao = request.json.get("acao")

    if acao == "parar":
        em_execucao = False
    elif acao == "pausar":
        pausado = True
    elif acao == "continuar":
        pausado = False
    return jsonify({"status": "ok"})

@app.route("/stream", methods=["POST"])
def stream():
    mensagem_modelo = request.form.get("mensagem")
    arquivo = request.files.get("arquivo")
    conteudo = arquivo.read().decode("utf-8").splitlines()  # <- corrigido aqui!

    def event_stream(mensagem_modelo, conteudo):
        global em_execucao, pausado
        em_execucao = True
        pausado = False

        total = len(conteudo)
        logs = []
        enviados = 0
        falhas = 0

        for i, linha in enumerate(conteudo, 1):
            if not em_execucao:
                logs.append("🛑 Envio interrompido pelo usuário.")
                yield f"data: {json.dumps({'logs': logs, 'enviados': enviados, 'falhas': falhas, 'progresso': int(i/total*100)})}\n\n"
                break

            while pausado:
                time.sleep(1)
                yield f"data: {json.dumps({'logs': logs, 'enviados': enviados, 'falhas': falhas, 'progresso': int(i/total*100), 'status': '⏸ Pausado'})}\n\n"

            linha = linha.strip()
            if not linha or ";" not in linha:
                logs.append(f"⚠️ [{i}] Ignorada: linha vazia ou mal formatada.")
                continue

            try:
                cpf, nome, telefone = [x.strip() for x in linha.split(";")]

                if not telefone.startswith("55") or len(telefone) < 12:
                    logs.append(f"⚠️ [{i}] Telefone inválido: {telefone}")
                    continue

                mensagem = mensagem_modelo.replace("{nome}", nome).replace("{cpf}", cpf)

                payload = {
                    "number": telefone,
                    "textMessage": {"text": mensagem}
                }
                headers = {
                    "apikey": API_KEY,
                    "Content-Type": "application/json"
                }

                logs.append(f"📤 [{i}] Enviando para {nome} ({telefone})...")
                response = requests.post(API_URL, json=payload, headers=headers)

                if response.status_code in [200, 201]:
                    logs.append(f"✅ [{i}] Enviado para {telefone}")
                    enviados += 1
                else:
                    logs.append(f"❌ [{i}] Falha para {telefone} | {response.status_code} | {response.text}")
                    falhas += 1

                logs.append("⏳ Aguardando 15 segundos...\n")
                yield f"data: {json.dumps({'logs': logs.copy(), 'enviados': enviados, 'falhas': falhas, 'progresso': int(i / total * 100)})}\n\n"
                time.sleep(15.7)

            except Exception as e:
                logs.append(f"❌ [{i}] Erro inesperado: {str(e)}")
                falhas += 1
                yield f"data: {json.dumps({'logs': logs.copy(), 'enviados': enviados, 'falhas': falhas, 'progresso': int(i / total * 100)})}\n\n"

        yield f"data: {json.dumps({'logs': logs, 'enviados': enviados, 'falhas': falhas, 'progresso': 100})}\n\n"

    return Response(event_stream(mensagem_modelo, conteudo), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run(debug=True)
