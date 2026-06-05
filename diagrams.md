# Booky.tn — UML Diagrams

---

## 1. Class Diagram

```mermaid
classDiagram
    direction TB

    class User {
        +int id
        +str username
        +str email
        +str password
        +bool is_staff
        +bool is_superuser
        +bool is_active
    }

    class Author {
        +int id
        +str name
        +str bio
    }

    class Category {
        +int id
        +str name
        +str description
        +str icon
    }

    class Book {
        +int id
        +str title
        +str isbn
        +int published_year
        +int available_copies
        +int total_copies
        +str cover_color
        +ImageField cover_image
        +Decimal rating
        +int pages
        +str language
        +datetime created_at
        +is_available() bool
    }

    class Conversation {
        +int id
        +str session_key
        +datetime created_at
        +datetime updated_at
    }

    class Message {
        +int id
        +str role
        +str content
        +datetime created_at
    }

    Author "1" --> "0..*" Book : writes
    Category "0..*" <--> "0..*" Book : categorizes
    Conversation "1" --> "1..*" Message : contains
    User ..> Conversation : owns via session
```

---

## 2. Use Case Diagram

```mermaid
flowchart LR
    Guest(["👤 Guest"])
    Member(["🔐 Member"])
    Admin(["🛡️ Admin"])
    Ollama(["🤖 Ollama LLM"])

    subgraph Public ["Public Access"]
        UC1(View Homepage)
        UC2(Browse Book List)
        UC3(Search Books)
        UC4(Filter by Category)
        UC5(View Book Detail)
        UC6(View Categories)
        UC7(Login)
        UC8(Sign Up)
    end

    subgraph Auth ["Authenticated Access"]
        UC9(Open AI Chat)
        UC10(Send Message to Booky)
        UC11(Clear Conversation)
        UC12(Select LLM Model)
    end

    subgraph AdminPanel ["Admin Panel"]
        UC13(View Dashboard)
        UC14(Manage Books)
        UC15(Manage Authors)
        UC16(Manage Categories)
        UC17(Manage Users)
        UC18(View Recent Actions)
    end

    Guest --> UC1
    Guest --> UC2
    Guest --> UC3
    Guest --> UC4
    Guest --> UC5
    Guest --> UC6
    Guest --> UC7
    Guest --> UC8

    Member --> UC1
    Member --> UC2
    Member --> UC3
    Member --> UC4
    Member --> UC5
    Member --> UC6
    Member --> UC9
    Member --> UC10
    Member --> UC11
    Member --> UC12

    Admin --> UC13
    Admin --> UC14
    Admin --> UC15
    Admin --> UC16
    Admin --> UC17
    Admin --> UC18

    UC10 --> Ollama
```

---

## 3. Sequence Diagrams

### 3.1 — User Login

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant LoginView
    participant AuthBackend
    participant DB as PostgreSQL

    User->>Browser: Navigate to /accounts/login/
    Browser->>LoginView: GET /accounts/login/
    LoginView-->>Browser: Render login.html

    User->>Browser: Submit username + password
    Browser->>LoginView: POST /accounts/login/
    LoginView->>AuthBackend: authenticate(username, password)
    AuthBackend->>DB: SELECT user WHERE username=?
    DB-->>AuthBackend: User record
    AuthBackend-->>LoginView: User object (or None)

    alt Credentials valid
        LoginView->>AuthBackend: login(request, user)
        AuthBackend->>DB: INSERT/UPDATE session
        LoginView-->>Browser: Redirect → /
        Browser->>User: Home page
    else Invalid credentials
        LoginView-->>Browser: Render login.html (error msg)
        Browser->>User: "Invalid username or password"
    end
```

---

### 3.2 — Book Search & Filter

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant BookListView
    participant DB as PostgreSQL

    User->>Browser: Go to /books/
    Browser->>BookListView: GET /books/
    BookListView->>DB: SELECT books + authors + categories
    DB-->>BookListView: All books
    BookListView-->>Browser: Render book_list.html (all books)

    User->>Browser: Type query "Dune" + select category
    Browser->>BookListView: GET /books/?q=Dune&category=3
    BookListView->>DB: SELECT books WHERE title ILIKE '%Dune%'\n OR author ILIKE '%Dune%'\n AND category_id=3
    DB-->>BookListView: Filtered books
    BookListView-->>Browser: Render book_list.html (filtered results)

    User->>Browser: Click on a book
    Browser->>BookListView: GET /books/<pk>/
    BookListView->>DB: SELECT book WHERE id=pk
    BookListView->>DB: SELECT related books (same category)
    DB-->>BookListView: Book + related books
    BookListView-->>Browser: Render book_detail.html
```

---

### 3.3 — AI Chat with Booky

```mermaid
sequenceDiagram
    actor User
    participant Browser
    participant ChatView
    participant DB as PostgreSQL
    participant OllamaAPI as Ollama LLM

    User->>Browser: Navigate to /chat/
    Browser->>ChatView: GET /chat/
    ChatView->>DB: get_or_create Conversation (session_key)
    ChatView->>DB: SELECT messages (history)
    ChatView-->>Browser: Render chat.html + message history

    User->>Browser: Type message "Recommend a sci-fi book"
    Browser->>ChatView: POST /chat/send/ {message, model}

    ChatView->>DB: INSERT Message (role=user)
    ChatView->>DB: SELECT all books + categories (library context)
    DB-->>ChatView: Full catalog
    ChatView->>ChatView: Build system prompt\n(SYSTEM_PROMPT + library catalog)

    ChatView->>OllamaAPI: POST /api/chat\n{model, messages, stream:true}

    loop Streaming tokens
        OllamaAPI-->>ChatView: chunk {message.content, done}
        ChatView-->>Browser: SSE: data: {"text": "token"}
        Browser->>User: Append token to chat bubble
    end

    OllamaAPI-->>ChatView: {done: true}
    ChatView->>DB: INSERT Message (role=assistant, full content)
    ChatView-->>Browser: SSE: data: {"done": true}
```

---

### 3.4 — Admin: Add a Book

```mermaid
sequenceDiagram
    actor Admin
    participant Browser
    participant AdminSite as Django Admin
    participant BookAdmin
    participant DB as PostgreSQL

    Admin->>Browser: Go to /admin/
    Browser->>AdminSite: GET /admin/
    AdminSite-->>Browser: Dashboard (stats, recent actions)

    Admin->>Browser: Click "Add Book"
    Browser->>BookAdmin: GET /admin/library/book/add/
    BookAdmin-->>Browser: Render Book form

    Admin->>Browser: Fill form + submit
    Browser->>BookAdmin: POST /admin/library/book/add/
    BookAdmin->>BookAdmin: Validate form fields
    BookAdmin->>DB: INSERT INTO library_book
    DB-->>BookAdmin: Book created (id)
    BookAdmin-->>Browser: Redirect + success message
    Browser->>Admin: "Book added successfully"
```
