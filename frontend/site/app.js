function makeSlider(selector, intervalMs) {
  const slides = Array.from(document.querySelectorAll(selector));
  if (slides.length === 0) return;

  let i = 0;
  slides.forEach((s, idx) => s.classList.toggle("active", idx === 0));

  setInterval(() => {
    slides[i].classList.remove("active");
    i = (i + 1) % slides.length;
    slides[i].classList.add("active");
  }, intervalMs);
}

makeSlider(".header-bg-slide", 3200);
makeSlider(".hero-bg-slide", 4500);

// === Chat ===
const chatForm = document.getElementById("chat-form");
const chatWindow = document.getElementById("chat-window");
const input = chatForm.querySelector("input");
const sendButton = chatForm.querySelector("button");
const sessionId = window.crypto?.randomUUID ? window.crypto.randomUUID() : String(Date.now());
const apiBase = window.location.origin === "null" ? "http://127.0.0.1:8000" : window.location.origin;

// Fonction pour ajouter un message
function addMessage(who, text) {
  const msg = document.createElement("div");
  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.textContent = text;

  if (who === "bot") {
    msg.classList.add("msg", "msg-bot");
    const avatar = document.createElement("div");
    avatar.classList.add("avatar");
    const img = document.createElement("img");
    img.src = "images/logo-AE.png";
    img.alt = "Assistant EPITECH";
    avatar.appendChild(img);
    msg.appendChild(avatar);
    msg.appendChild(bubble);
  } else {
    msg.classList.add("msg", "msg-user");
    const avatar = document.createElement("div");
    avatar.classList.add("avatar", "user");
    avatar.setAttribute("aria-hidden", "true");
    avatar.textContent = "Vous";
    msg.appendChild(bubble);
    msg.appendChild(avatar);
  }

  chatWindow.appendChild(msg);
  // Scroll automatique
  chatWindow.scrollTop = chatWindow.scrollHeight;
  return bubble; // pour pouvoir modifier le texte plus tard
}

// Événement sur le formulaire / bouton
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  
  // Ajout du message utilisateur
  addMessage("user", text);
  input.value = "";

  // Désactiver le bouton envoyer
  sendButton.disabled = true;

  // Message bot temporaire "L'IA réfléchit…"
  const bubble = addMessage("bot", "Recherche en cours...");

  try {
    const resp = await fetch(`${apiBase}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, session_id: sessionId }),
    });

    if (!resp.ok) {
      throw new Error("API error");
    }

    const data = await resp.json();
    const answer = data.answer || "Je n'ai pas de réponse pour l'instant.";
    bubble.textContent = answer;

    if (Array.isArray(data.sources) && data.sources.length > 0) {
      const sources = document.createElement("div");
      sources.classList.add("sources");
      const title = document.createElement("div");
      title.classList.add("sources-title");
      title.textContent = "Sources";
      sources.appendChild(title);

      data.sources.slice(0, 4).forEach((source) => {
        const item = document.createElement("div");
        const link = document.createElement("a");
        link.href = source.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = source.url;
        item.appendChild(link);
        sources.appendChild(item);
      });

      bubble.appendChild(sources);
    }
  } catch (err) {
    bubble.textContent = "Erreur : impossible de joindre le serveur.";
    console.error(err);
  } finally {
    sendButton.disabled = false;
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }
});


  // la réponse réelle du backend
  /*
  
 // Message bot temporaire
  const thinkingMessage = document.createElement("div");
  thinkingMessage.classList.add("msg", "msg-bot");
  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  const img = document.createElement("img");
  img.src = "images/logo-AE.png";
  img.alt = "Assistant EPITECH";
  avatar.appendChild(img);
  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.textContent = "L’IA réfléchit…";
  thinkingMessage.appendChild(avatar);
  thinkingMessage.appendChild(bubble);
  chatWindow.appendChild(thinkingMessage);
  chatWindow.scrollTop = chatWindow.scrollHeight;

  // === Simulation fetch avec timeout ===
  const controller = new AbortController();
  const timeout = 4000; // 4 secondes max pour la réponse
  const timeoutId = setTimeout(() => {
    controller.abort(); // Annule la requête si délai dépassé
  }, timeout);

  fetch("http://127.0.0.1:5000/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message: text }),
    signal: controller.signal
  })
    .then(res => res.json())
    .then(data => {
      clearTimeout(timeoutId); // Annuler le timeout si réponse reçue
      bubble.textContent = data.response; // Affiche la réponse du backend
      sendButton.disabled = false; // réactiver le bouton
      chatWindow.scrollTop = chatWindow.scrollHeight;
    })
    .catch(err => {
      // Si fetch échoue ou timeout
      if (err.name === "AbortError") {
        bubble.textContent = "Erreur : le serveur ne répond pas (timeout).";
      } else {
        bubble.textContent = "Erreur : impossible de joindre le serveur.";
      }
      sendButton.disabled = false; // réactiver le bouton même en erreur
      chatWindow.scrollTop = chatWindow.scrollHeight;
      console.error(err);
    });
});

 */


// Le bouton submit declenche deja le submit du formulaire.
