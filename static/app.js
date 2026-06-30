const chatArea = document.getElementById("chatArea");
const chatForm = document.getElementById("chatForm");
const messageInput = document.getElementById("messageInput");


function scrollToBottom() {
    chatArea.scrollTop = chatArea.scrollHeight;
}


function createMessage(role, text, isTyping = false) {
    const row = document.createElement("div");
    row.className = `message-row ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "message-bubble";

    if (isTyping) {
        bubble.classList.add("typing");
    }

    bubble.textContent = text;
    row.appendChild(bubble);
    chatArea.appendChild(row);

    scrollToBottom();

    return row;
}


async function loadHistory() {
    try {
        const res = await fetch("/history");
        const data = await res.json();

        if (!data.ok) {
            return;
        }

        data.messages.forEach(msg => {
            createMessage(msg.role, msg.content);
        });

        scrollToBottom();

    } catch (err) {
        console.error(err);
    }
}


function resizeTextarea() {
    messageInput.style.height = "auto";
    messageInput.style.height = messageInput.scrollHeight + "px";
}


messageInput.addEventListener("input", resizeTextarea);


messageInput.addEventListener("focus", () => {
    setTimeout(() => {
        messageInput.scrollIntoView({
            behavior: "smooth",
            block: "center"
        });

        scrollToBottom();
    }, 300);
});


if (window.visualViewport) {
    window.visualViewport.addEventListener("resize", () => {
        document.documentElement.style.height =
            window.visualViewport.height + "px";

        document.body.style.height =
            window.visualViewport.height + "px";

        setTimeout(() => {
            scrollToBottom();
        }, 100);
    });
}


chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    const message = messageInput.value.trim();

    if (!message) {
        return;
    }

    createMessage("user", message);

    messageInput.value = "";
    messageInput.style.height = "auto";

    const typingRow = createMessage(
        "assistant",
        "...",
        true
    );

    try {
        const delay = 700 + Math.floor(Math.random() * 1200);
        await new Promise(resolve => setTimeout(resolve, delay));

        const res = await fetch("/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: message
            })
        });

        const data = await res.json();

        typingRow.remove();

        if (data.ok) {
            createMessage("assistant", data.reply);
        } else {
            createMessage("assistant", "今無理。もう一回送れ。");
        }

    } catch (err) {
        console.error(err);

        typingRow.remove();

        createMessage("assistant", "通信切れてる。");
    }
});


async function clearChat() {
    const ok = confirm("会話履歴を削除する？");

    if (!ok) {
        return;
    }

    try {
        await fetch("/clear", {
            method: "POST"
        });

        chatArea.innerHTML = `
            <div class="date-label">今日</div>
        `;

    } catch (err) {
        console.error(err);
    }
}


loadHistory();