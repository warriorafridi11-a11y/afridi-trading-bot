// Chat window: send a message to the bot without reloading the page.
const form = document.getElementById("chat-form");
const input = document.getElementById("chat-input");
const box = document.getElementById("chat-box");
const LOGO = "/static/logo.png";

function scrollDown() {
  box.scrollTop = box.scrollHeight;
}

function addMessage(text, who) {
  const row = document.createElement("div");
  row.className = "msg-row " + who;
  if (who === "bot") {
    const img = document.createElement("img");
    img.className = "msg-avatar";
    img.src = LOGO;
    img.alt = "";
    img.onerror = function () { this.style.display = "none"; };
    row.appendChild(img);
  }
  const div = document.createElement("div");
  div.className = "msg " + who;
  div.textContent = text;
  row.appendChild(div);
  box.appendChild(row);
  scrollDown();
}

function showTyping() {
  const row = document.createElement("div");
  row.className = "msg-row bot";
  row.id = "typing-row";
  const img = document.createElement("img");
  img.className = "msg-avatar";
  img.src = LOGO;
  img.alt = "";
  img.onerror = function () { this.style.display = "none"; };
  row.appendChild(img);
  const dots = document.createElement("div");
  dots.className = "msg bot typing";
  dots.innerHTML = "<span></span><span></span><span></span>";
  row.appendChild(dots);
  box.appendChild(row);
  scrollDown();
}

function hideTyping() {
  const row = document.getElementById("typing-row");
  if (row) row.remove();
}

function addPhoto(url) {
  const row = document.createElement("div");
  row.className = "msg-row bot";
  const img = document.createElement("img");
  img.className = "chat-photo";
  img.src = url;
  img.alt = "Photo of the car";
  img.loading = "lazy";
  img.onerror = function () { row.remove(); };
  row.appendChild(img);
  box.appendChild(row);
  scrollDown();
}

async function sendMessage(text) {
  addMessage(text, "user");
  showTyping();
  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text }),
    });
    const data = await res.json();
    hideTyping();
    addMessage(data.reply, "bot");
    if (data.photo) addPhoto(data.photo);
  } catch (err) {
    hideTyping();
    addMessage("Sorry, I could not reach the bot. Please try again.", "bot");
  }
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  input.value = "";
  sendMessage(text);
});

// Hint chips: tap one to ask it at once.
document.querySelectorAll(".hint-btn").forEach((btn) => {
  btn.addEventListener("click", () => sendMessage(btn.dataset.q));
});

// "Ask the bot about this car" buttons link here with ?ask=...
const params = new URLSearchParams(window.location.search);
const asked = params.get("ask");
if (asked) {
  input.value = asked;
  sendMessage(asked);
  // Clean the address bar so a refresh does not ask again.
  window.history.replaceState({}, "", "/");
}
