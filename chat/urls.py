from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_view, name='chat'),
    path('send/', views.send_message, name='send_message'),
    path('clear/', views.clear_conversation, name='clear'),
    path('ollama-models/', views.ollama_models_api, name='ollama_models'),
]
