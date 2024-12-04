import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

app = Flask(__name__)
CORS(app)

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ALGOLIA_API_KEY = os.getenv("ALGOLIA_API_KEY")
ALGOLIA_APP_ID = os.getenv("ALGOLIA_APP_ID")

ALGOLIA_INDEX_NAME = "dev_oceanmd"

# Step 2: Generate Keywords with GPT
def generate_keywords(query):
    gpt_payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant trained in healthcare IT at OceanMD. Determine ONLY THE THREE [3] most relevant individual keywords from queries, knowing that the terms will be used to query a database of support articles, thus they need to be selected for the best chance of finding the most relevant content."
            },
            {
                "role": "user",
                "content": f"Given the context of healthcare IT, determine the THREE [3] most relevant keywords (formatted as a simple comma-separated list) from this support query: {query}"
            }
        ]
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json=gpt_payload
    )
    response_data = response.json()
    return response_data["choices"][0]["message"]["content"]

# Step 3: Search Algolia with Keywords
def search_algolia(keywords):
    algolia_payload = {
        "query": keywords,
        "hitsPerPage": 5,
        "filters": "NOT category.title:'Announcements'"
    }

    response = requests.post(
        f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX_NAME}/query",
        headers={
            "X-Algolia-API-Key": ALGOLIA_API_KEY,
            "X-Algolia-Application-Id": ALGOLIA_APP_ID,
            "Content-Type": "application/json"
        },
        json=algolia_payload
    )
    articles = response.json()["hits"]

    # Generate proper URLs for each article
    for article in articles:
        article["link"] = f"https://support.cognisantmd.com/hc/en-us/articles/{article['id']}"

    return articles

# Step 4: Generate Final Response with GPT
def generate_final_response(query, articles):
    # Prepare article details with titles and links
    article_list = "".join(
        f"<li><a href='{article['link']}' target='_blank'>{article['title']}</a></li>"
        for article in articles
    )

    gpt_payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant trained in healthcare IT and working at OceanMD where you manage the knowledge base. You are an expert in answering user inquiries about Ocean, the platform containing several digital health tools like EMR-integrated eReferrals and secure patient messaging and forms. When asked a question, you carefully consider the relevant documentation before synthesizing your answer. You always provide all your sources as links at the end of your responses. You aren't afraid to say when you aren't sure or don't have enough information. Provide your answers formatted in HTML for email, including proper HTML tags for headings, lists, bold text, and hyperlinks."
            },
            {
                "role": "user",
                "content": f"An Ocean user has sent you this inquiry: {query}. You performed a search through the Ocean documentation and identified the following articles:<ul>{article_list}</ul>. If the articles are not deemed relevant, or there are no results, inform the inquirer that you cannot help them at this time."
            }
        ]
    }

    response = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json=gpt_payload
    )
    response_data = response.json()
    return response_data["choices"][0]["message"]["content"]

# Route for Handling Queries
@app.route("/query", methods=["POST"])
def handle_query():
    data = request.json
    user_query = data.get("query", "")

    # Step 2: Generate Keywords
    keywords = generate_keywords(user_query)

    # Step 3: Search Algolia
    articles = search_algolia(keywords)

    # Step 4: Generate Final Response
    final_response = generate_final_response(user_query, articles)

    return jsonify({"response": final_response})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # Default to port 5000 for local testing
    app.run(host="0.0.0.0", port=port)
