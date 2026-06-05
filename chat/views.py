import json
import requests
from django.shortcuts import render
from django.http import JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.conf import settings
from .models import Conversation, Message
from library.models import Book, Category


def get_library_context():
    books = Book.objects.select_related('author', 'category').all()
    lines = ["Available books in our library:"]
    for book in books:
        avail = "available" if book.is_available else "not available"
        lines.append(
            f"- '{book.title}' by {book.author.name} "
            f"(Categories: {', '.join(c.name for c in book.categories.all()) or 'N/A'}, "
            f"Year: {book.published_year or 'N/A'}, "
            f"Rating: {book.rating}/5, {avail}). "
            f"Description: {book.description[:150]}..."
        )
    categories = Category.objects.all()
    lines.append("\nCategories: " + ", ".join(c.name for c in categories))
    return "\n".join(lines)


SYSTEM_PROMPT = """You are an intelligent library assistant named "Booky". You help users discover books, get recommendations, and learn about the library's collection.

You have access to the current library catalog. Be friendly, knowledgeable, and enthusiastic about books. When recommending books, mention specific titles from the catalog when relevant.

You can:
- Recommend books based on interests, mood, or genre
- Provide information about specific books and authors
- Help users find available books
- Suggest reading lists on topics
- Discuss book themes, summaries, and reviews
- Help with borrowing questions

Always be warm, encouraging, and passionate about reading. Keep responses concise but informative."""


def get_ollama_models():
    try:
        resp = requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3)
        if resp.status_code == 200:
            return [m['name'] for m in resp.json().get('models', [])]
    except requests.RequestException:
        pass
    return []


def ollama_available():
    try:
        requests.get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=2)
        return True
    except requests.RequestException:
        return False


def _stream_ollama(model, api_messages, full_system, conversation):
    ollama_messages = [{'role': 'system', 'content': full_system}] + api_messages
    full_response = []
    try:
        with requests.post(
            f"{settings.OLLAMA_BASE_URL}/api/chat",
            json={'model': model, 'messages': ollama_messages, 'stream': True},
            stream=True,
            timeout=120,
        ) as resp:
            resp.raise_for_status()
            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                try:
                    chunk = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue
                token = chunk.get('message', {}).get('content', '')
                if token:
                    full_response.append(token)
                    yield f"data: {json.dumps({'text': token})}\n\n"
                if chunk.get('done'):
                    break
    except requests.RequestException as e:
        yield f"data: {json.dumps({'error': f'Ollama error: {e}'})}\n\n"
        return

    Message.objects.create(
        conversation=conversation,
        role='assistant',
        content=''.join(full_response),
    )
    yield f"data: {json.dumps({'done': True})}\n\n"


@login_required
def chat_view(request):
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    conversation, _ = Conversation.objects.get_or_create(session_key=session_key)
    messages = conversation.messages.all()
    ollama_models = get_ollama_models()
    return render(request, 'chat/chat.html', {
        'conversation': conversation,
        'messages': messages,
        'ollama_models': ollama_models,
        'ollama_default': settings.OLLAMA_DEFAULT_MODEL,
        'ollama_up': bool(ollama_models),
    })


@login_required
@csrf_exempt
def send_message(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
        user_content = data.get('message', '').strip()
        model = data.get('model', settings.OLLAMA_DEFAULT_MODEL)
        if not user_content:
            return JsonResponse({'error': 'Empty message'}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    conversation, _ = Conversation.objects.get_or_create(session_key=session_key)

    Message.objects.create(conversation=conversation, role='user', content=user_content)

    history = list(conversation.messages.order_by('created_at').values('role', 'content'))
    api_messages = [{'role': m['role'], 'content': m['content']} for m in history]
    full_system = f"{SYSTEM_PROMPT}\n\n{get_library_context()}"

    generator = _stream_ollama(model, api_messages, full_system, conversation)
    response = StreamingHttpResponse(generator, content_type='text/event-stream')
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response


@csrf_exempt
def ollama_models_api(request):
    return JsonResponse({'models': get_ollama_models(), 'up': ollama_available()})


@csrf_exempt
def clear_conversation(request):
    if request.method == 'POST':
        if request.session.session_key:
            Conversation.objects.filter(session_key=request.session.session_key).delete()
        return JsonResponse({'status': 'cleared'})
    return JsonResponse({'error': 'Method not allowed'}, status=405)
