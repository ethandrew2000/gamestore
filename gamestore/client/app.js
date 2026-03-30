const API_BASE = "http://localhost:5000";
const CARDS_URL = `${API_BASE}/cards`;

function getSessionId() {
    return localStorage.getItem("session_id");
}

function getUser() {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
}

function saveSession(session_id, user) {
    localStorage.setItem("session_id", session_id);
    localStorage.setItem("user", JSON.stringify(user));
}

function clearSession() {
    localStorage.removeItem("session_id");
    localStorage.removeItem("user");
}

function isLoggedIn() {
    return !!getSessionId();
}

function isAdmin() {
    const user = getUser();
    return !!user && user.role === "admin";
}

function authFetch(url, options) {
    options = options || {};

    const session_id = getSessionId();
    const headers = Object.assign(
        { "Content-Type": "application/json" },
        options.headers || {}
    );

    if (session_id) {
        headers["X-Session-ID"] = session_id;
    }

    return fetch(url, Object.assign({}, options, { headers: headers }));
}

function updateNav() {
    const loggedIn = isLoggedIn();
    const admin = isAdmin();
    const user = getUser();

    document.querySelectorAll("[data-auth='true']").forEach(function (el) {
        el.style.display = loggedIn ? "" : "none";
    });

    document.querySelectorAll("[data-auth='false']").forEach(function (el) {
        el.style.display = loggedIn ? "none" : "";
    });

    document.querySelectorAll("[data-role='admin']").forEach(function (el) {
        el.style.display = admin ? "" : "none";
    });

    const greeting = document.getElementById("userGreeting");
    if (greeting && user) {
        greeting.textContent = "Welcome, " + user.first_name + " (" + user.role + ")";
        greeting.style.display = "";
    } else if (greeting) {
        greeting.style.display = "none";
    }
}

function requireLogin(redirectTo) {
    if (!redirectTo) redirectTo = "login.html";
    if (!isLoggedIn()) {
        window.location.href = redirectTo;
    }
}

function requireAdmin() {
    if (!isLoggedIn()) {
        window.location.href = "login.html";
        return;
    }

    if (!isAdmin()) {
        window.location.href = "user.html";
    }
}

function setupRegisterForm() {
    const form = document.getElementById("registerForm");
    if (!form) return;

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        clearMessage("registerMsg");

        const userData = {
            first_name: document.getElementById("first_name").value.trim(),
            last_name: document.getElementById("last_name").value.trim(),
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value
        };

        fetch(`${API_BASE}/users`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(userData)
        })
        .then(function (res) {
            return res.json().then(function (data) {
                return { ok: res.ok, status: res.status, data: data };
            });
        })
        .then(function (result) {
            if (result.ok) {
                showMessage("registerMsg", "Registration successful! Redirecting to login...", "success");
                form.reset();
                setTimeout(function () {
                    window.location.href = "login.html";
                }, 1500);
            } else {
                showMessage("registerMsg", result.data.error || "Registration failed.", "error");
            }
        })
        .catch(function () {
            showMessage("registerMsg", "Could not connect to server.", "error");
        });
    });
}

function setupLoginForm() {
    const form = document.getElementById("loginForm");
    if (!form) return;

    if (isLoggedIn()) {
        const user = getUser();
        if (user && user.role === "admin") {
            window.location.href = "index.html";
        } else {
            window.location.href = "user.html";
        }
        return;
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();
        clearMessage("loginMsg");

        const credentials = {
            email: document.getElementById("email").value.trim(),
            password: document.getElementById("password").value
        };

        fetch(`${API_BASE}/auth/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials)
        })
        .then(function (res) {
            return res.json().then(function (data) {
                return { ok: res.ok, status: res.status, data: data };
            });
        })
        .then(function (result) {
            if (result.ok) {
                saveSession(result.data.session_id, result.data.user);
                showMessage("loginMsg", "Login successful! Redirecting...", "success");

                setTimeout(function () {
                    if (result.data.user.role === "admin") {
                        window.location.href = "index.html";
                    } else {
                        window.location.href = "user.html";
                    }
                }, 1000);
            } else {
                showMessage("loginMsg", result.data.error || "Login failed.", "error");
            }
        })
        .catch(function () {
            showMessage("loginMsg", "Could not connect to server.", "error");
        });
    });
}

function logout() {
    authFetch(`${API_BASE}/auth/logout`, { method: "POST" })
        .catch(function () {})
        .finally(function () {
            clearSession();
            window.location.href = "login.html";
        });
}

function loadCards() {
    authFetch(CARDS_URL)
        .then(function (res) {
            if (res.status === 401) {
                window.location.href = "login.html";
                return null;
            }

            if (res.status === 403) {
                window.location.href = "user.html";
                return null;
            }

            return res.json();
        })
        .then(function (cards) {
            if (!cards) return;

            const tbody = document.getElementById("cardTableBody");
            if (!tbody) return;

            tbody.innerHTML = "";

            cards.forEach(function (card) {
                const row = document.createElement("tr");
                row.innerHTML = `
                    <td>${card.name}</td>
                    <td>${card.set_name}</td>
                    <td>$${parseFloat(card.price).toFixed(2)}</td>
                    <td>${card.quantity}</td>
                    <td>
                        <button onclick="editCard(${card.id})">Edit</button>
                        <button class="btn-danger" onclick="deleteCard(${card.id})">Delete</button>
                    </td>
                `;
                tbody.appendChild(row);
            });
        })
        .catch(function (err) {
            console.error("Error loading cards:", err);
        });
}

function loadCardGrid() {
    const container = document.getElementById("cardContainer");
    if (!container) return;

    container.innerHTML = "<p>Loading inventory...</p>";

    fetch(CARDS_URL, {
        headers: {
            "Content-Type": "application/json"
        }
    })
    .then(function (res) {
        if (!res.ok) {
            throw new Error("Failed to load cards");
        }
        return res.json();
    })
    .then(function (cards) {
        container.innerHTML = "";

        if (!cards || cards.length === 0) {
            container.innerHTML = "<p style='color:var(--text-muted)'>No cards in inventory yet.</p>";
            return;
        }

        cards.forEach(function (card) {
            const div = document.createElement("div");
            div.className = "inventory-card";
            div.innerHTML = `
                <h2>${card.name}</h2>
                <p><strong>Set:</strong> ${card.set_name}</p>
                <p><strong>Condition:</strong> ${card.condition}</p>
                <p><strong>Price:</strong> $${parseFloat(card.price).toFixed(2)}</p>
                <p><strong>Quantity:</strong> ${card.quantity}</p>
                <p><strong>Rarity:</strong> ${card.rarity}</p>
            `;
            container.appendChild(div);
        });
    })
    .catch(function (err) {
        console.error("Error loading card grid:", err);
        container.innerHTML = "<p style='color:red;'>Could not load inventory.</p>";
    });
}

function deleteCard(id) {
    if (!isAdmin()) return;
    if (!confirm("Are you sure you want to delete this card?")) return;

    authFetch(`${CARDS_URL}/${id}`, {
        method: "DELETE"
    })
    .then(function (res) {
        if (res.status === 401) {
            window.location.href = "login.html";
            return;
        }

        if (res.status === 403) {
            window.location.href = "user.html";
            return;
        }

        loadCards();
    })
    .catch(function (err) {
        console.error("Error deleting card:", err);
    });
}

function editCard(id) {
    if (!isAdmin()) return;
    window.location.href = `add.html?id=${id}`;
}

function setupForm() {
    const form = document.getElementById("cardForm");
    if (!form) return;

    const params = new URLSearchParams(window.location.search);
    const id = params.get("id");

    if (id) {
        const title = document.getElementById("formTitle");
        if (title) title.innerText = "Edit Card";
        loadCardIntoForm(id);
    }

    form.addEventListener("submit", function (e) {
        e.preventDefault();

        const cardData = {
            name: document.getElementById("name").value,
            set_name: document.getElementById("set_name").value,
            condition: document.getElementById("condition").value,
            price: parseFloat(document.getElementById("price").value),
            quantity: parseInt(document.getElementById("quantity").value),
            rarity: document.getElementById("rarity").value
        };

        const method = id ? "PUT" : "POST";
        const url = id ? `${CARDS_URL}/${id}` : CARDS_URL;

        authFetch(url, {
            method: method,
            body: JSON.stringify(cardData)
        })
        .then(function (res) {
            if (res.status === 401) {
                window.location.href = "login.html";
                return;
            }

            if (res.status === 403) {
                window.location.href = "user.html";
                return;
            }

            window.location.href = "index.html";
        })
        .catch(function (err) {
            console.error("Error saving card:", err);
        });
    });
}

function loadCardIntoForm(id) {
    fetch(`${CARDS_URL}/${id}`, {
        headers: {
            "Content-Type": "application/json"
        }
    })
    .then(function (res) {
        if (!res.ok) {
            throw new Error("Failed to load card");
        }
        return res.json();
    })
    .then(function (card) {
        document.getElementById("name").value = card.name;
        document.getElementById("set_name").value = card.set_name;
        document.getElementById("condition").value = card.condition;
        document.getElementById("price").value = card.price;
        document.getElementById("quantity").value = card.quantity;
        document.getElementById("rarity").value = card.rarity;
    })
    .catch(function (err) {
        console.error("Error loading card:", err);
    });
}

function showMessage(elementId, text, type) {
    const el = document.getElementById(elementId);
    if (!el) return;

    el.textContent = text;
    el.className = `msg msg-${type}`;
    el.style.display = "";
}

function clearMessage(elementId) {
    const el = document.getElementById(elementId);
    if (!el) return;

    el.textContent = "";
    el.style.display = "none";
}

document.addEventListener("DOMContentLoaded", function () {
    updateNav();

    const page = document.body.dataset.page;

    if (page === "inventory") {
        requireAdmin();
        loadCards();
    }

    if (page === "home") {
        loadCardGrid();
    }

    if (page === "add") {
        requireAdmin();
        setupForm();
    }

    if (page === "register") {
        setupRegisterForm();
    }

    if (page === "login") {
        setupLoginForm();
    }

    const logoutBtn = document.getElementById("logoutBtn");
    if (logoutBtn) {
        logoutBtn.addEventListener("click", logout);
    }
});