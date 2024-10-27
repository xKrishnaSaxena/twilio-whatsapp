from flask import Flask, request, Response, url_for
from twilio.twiml.messaging_response import MessagingResponse
from pymilvus import Collection, connections
import os
from dotenv import load_dotenv
from embedding import get_embedding
import requests
from datetime import datetime, timezone
from io import BytesIO
from uuid import uuid4
from weasyprint import HTML

load_dotenv()

app = Flask(__name__)

connections.connect(
    alias="default",
    host=os.getenv("MILVUS_HOST", "localhost"),
    port=os.getenv("MILVUS_PORT", "19530")
)

collection = Collection(name="whatsapp_messages")

FASTAPI_URL = os.getenv("FASTAPI_URL", "http://localhost:8000/chat/")

sessions = {}






@app.route("/webhook", methods=['POST'])
def webhook():
    from_number = request.form.get('From')
    body = request.form.get('Body')
    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"Received message from {from_number}: {body}")

    embedding = get_embedding(body)
    if not embedding:
        print("Failed to generate embedding.")
        resp = MessagingResponse()
        resp.message("Sorry, something went wrong while processing your message.")
        return Response(str(resp), mimetype='application/xml')

    entities = [[from_number], [body], [timestamp], [embedding]]
    try:
        collection.insert(entities)
        collection.flush()  
    except Exception as e:
        print(f"Error inserting into Milvus: {e}")
        resp = MessagingResponse()
        resp.message("Sorry, there was an error processing your message.")
        return Response(str(resp), mimetype='application/xml')

    if from_number not in sessions:
        sessions[from_number] = {"messages": []}

    sessions[from_number]["messages"].append({"role": "user", "content": body})

    state_payload = {
        "messages": sessions[from_number]["messages"],
        "conversation_state": sessions[from_number].get("conversation_state", {})
    }

    try:
        chat_response = requests.post(FASTAPI_URL, json=state_payload, timeout=10)
        chat_response.raise_for_status()

       
        if "application/pdf" in chat_response.headers.get("Content-Type", ""):
            pdf_filename = f"invoice_{uuid4().hex}.pdf"
            pdf_path = os.path.join("static", pdf_filename)

            os.makedirs("static", exist_ok=True)

            with open(pdf_path, 'wb') as pdf_file:
                pdf_file.write(chat_response.content)

            
            media_url = url_for('static', filename=pdf_filename, _external=True)

            
            resp = MessagingResponse()
            message = resp.message("Your invoice has been generated. Download it above:")
            message.media(media_url)
            return Response(str(resp), mimetype='application/xml')

        
        chat_data = chat_response.json()
        sessions[from_number]["messages"] = chat_data.get("messages", sessions[from_number]["messages"])
        sessions[from_number]["conversation_state"] = chat_data.get("conversation_state", {})

        messages = sessions[from_number]["messages"]
        bot_response = "I'm sorry, I don't understand."
        for message in reversed(messages):
            if message.get("role") == "assistant":
                bot_response = message.get("content", bot_response)
                break
        resp=MessagingResponse()
        resp.message(bot_response)

    except requests.exceptions.RequestException as e:
        print(f"Error making request to FastAPI: {e}")
        bot_response = "I'm sorry, I am having trouble connecting to the server."
        resp = MessagingResponse()
        resp.message(bot_response)
    return Response(str(resp), mimetype='application/xml')


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
