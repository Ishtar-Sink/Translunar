// Cliente do painel: API com CSRF, login, tema e registro de seções.

const METODOS_QUE_ALTERAM = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const CHAVE_TEMA = "translunar-tema";

let csrfToken = null;
const secoes = new Map();

const $ = (id) => document.getElementById(id);

function mostrarVista(vista) {
  $("login").hidden = vista !== "login";
  $("painel").hidden = vista !== "painel";
}

export function showToast(mensagem, tipo = "info") {
  const toast = document.createElement("div");
  toast.className = `toast toast-${tipo}`;
  toast.textContent = mensagem;
  $("toasts").append(toast);
  setTimeout(() => toast.remove(), 5000);
}

export async function api(path, options = {}) {
  const metodo = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers || {});
  const corpo = options.body;
  const ehJson = corpo !== undefined && typeof corpo !== "string" && !(corpo instanceof FormData);
  if (ehJson) headers.set("Content-Type", "application/json");
  if (METODOS_QUE_ALTERAM.has(metodo) && csrfToken) headers.set("X-CSRF-Token", csrfToken);
  const resposta = await fetch(path, {
    ...options,
    method: metodo,
    headers,
    body: ehJson ? JSON.stringify(corpo) : corpo,
    credentials: "same-origin",
  });
  if (resposta.status === 401 && path !== "/api/login") {
    csrfToken = null;
    mostrarVista("login");
  }
  return resposta;
}

const ouvintes = new Set();
let fonteEventos = null;

function conectarEventos() {
  const fonte = new EventSource("/api/eventos");
  fonteEventos = fonte;
  fonte.addEventListener("progresso", (evento) => {
    let dados = null;
    try {
      dados = JSON.parse(evento.data);
    } catch {
      return;
    }
    for (const ouvinte of ouvintes) ouvinte(dados);
  });
  fonte.onerror = () => {
    // Erro HTTP (sessão expirada, reinício) fecha a fonte: reconecta depois de uma pausa.
    if (fonte.readyState !== EventSource.CLOSED) return;
    if (fonteEventos === fonte) fonteEventos = null;
    setTimeout(() => {
      if (ouvintes.size && !fonteEventos) conectarEventos();
    }, 3000);
  };
}

// Um único EventSource compartilhado pelas seções; devolve a função que cancela a assinatura.
export function subscribeEvents(callback) {
  ouvintes.add(callback);
  if (!fonteEventos) conectarEventos();
  return () => {
    ouvintes.delete(callback);
    if (!ouvintes.size && fonteEventos) {
      fonteEventos.close();
      fonteEventos = null;
    }
  };
}

const ICONE_PADRAO = '<circle cx="12" cy="12" r="9"/>';
const ICONE_LUA = '<path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/>';
const ICONE_SOL =
  '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>';

let secaoAtiva = null;

function svgIcone(conteudo) {
  return `<svg class="icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${conteudo}</svg>`;
}

// Os ícones são strings SVG escritas no código, nunca vindas do servidor.
export function registerSection(id, render, opcoes = {}) {
  const { label = id, icon = ICONE_PADRAO, subtitle = "" } = opcoes;
  secoes.set(id, { render, label, icon, subtitle });
  montarNav();
  if (!$("painel").hidden) {
    render($(id));
    ativarSecao(secaoAtiva && secoes.has(secaoAtiva) ? secaoAtiva : idInicial(), false);
  }
}

function idInicial() {
  const doHash = decodeURIComponent(location.hash.slice(1));
  return secoes.has(doHash) ? doHash : secoes.keys().next().value;
}

function montarNav() {
  const nav = $("nav");
  nav.replaceChildren();
  for (const [id, secao] of secoes) {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "nav-item";
    item.dataset.secao = id;
    item.innerHTML = svgIcone(secao.icon);
    const rotulo = document.createElement("span");
    rotulo.textContent = secao.label;
    item.append(rotulo);
    item.addEventListener("click", () => ativarSecao(id, true));
    nav.append(item);
  }
}

// Troca a seção visível (usada por uma seção para abrir outra).
export function showSection(id) {
  if (secoes.has(id)) ativarSecao(id, true);
}

function ativarSecao(id, gravarHash) {
  const vazio = !id || !secoes.has(id);
  $("estado-vazio").hidden = !vazio;
  $("pagina-titulo").textContent = vazio ? "Translunar" : secoes.get(id).label;
  $("pagina-subtitulo").textContent = vazio ? "" : secoes.get(id).subtitle;
  $("pagina-subtitulo").hidden = vazio || !secoes.get(id).subtitle;
  if (vazio) return;
  secaoAtiva = id;
  for (const outra of secoes.keys()) {
    const elemento = $(outra);
    if (elemento) elemento.hidden = outra !== id;
  }
  for (const item of $("nav").children) {
    const ativo = item.dataset.secao === id;
    item.classList.toggle("active", ativo);
    if (ativo) item.setAttribute("aria-current", "page");
    else item.removeAttribute("aria-current");
  }
  if (gravarHash && location.hash.slice(1) !== id) history.replaceState(null, "", `#${id}`);
  // Cada seção recarrega os próprios dados ao aparecer: o que mudou em outra seção (um envio,
  // uma exclusão) não deixa a tela velha.
  document.dispatchEvent(new CustomEvent("secao-ativada", { detail: { id } }));
}

function renderizarSecoes() {
  for (const [id, secao] of secoes) {
    const elemento = $(id);
    if (elemento) secao.render(elemento);
  }
  montarNav();
  ativarSecao(idInicial(), false);
}

function mostrarPainel(csrf) {
  csrfToken = csrf;
  mostrarVista("painel");
  renderizarSecoes();
}

function mostrarErroLogin(texto) {
  const caixa = $("login-erro");
  caixa.textContent = texto;
  caixa.hidden = !texto;
}

async function entrar(evento) {
  evento.preventDefault();
  mostrarErroLogin("");
  const campo = $("login-senha");
  const resposta = await api("/api/login", { method: "POST", body: { senha: campo.value } });
  if (resposta.ok) {
    const dados = await resposta.json();
    campo.value = "";
    mostrarPainel(dados.csrf);
  } else if (resposta.status === 429) {
    const segundos = Number(resposta.headers.get("Retry-After")) || 60;
    const minutos = Math.ceil(segundos / 60);
    mostrarErroLogin(`Muitas tentativas. Tente de novo em ${minutos} minutos.`);
  } else if (resposta.status === 503) {
    mostrarErroLogin("A senha do painel não está configurada no servidor.");
  } else {
    mostrarErroLogin("Senha incorreta.");
  }
}

async function sair() {
  await api("/api/logout", { method: "POST" });
  csrfToken = null;
  mostrarVista("login");
}

function temaSalvo() {
  try {
    return localStorage.getItem(CHAVE_TEMA);
  } catch {
    return null;
  }
}

function aplicarTema(tema) {
  document.documentElement.dataset.theme = tema;
  const escuro = tema === "dark";
  $("btn-tema-rotulo").textContent = escuro ? "Tema claro" : "Tema escuro";
  $("btn-tema-icone").innerHTML = svgIcone(escuro ? ICONE_SOL : ICONE_LUA);
}

function iniciarTema() {
  const salvo = temaSalvo();
  if (salvo === "light" || salvo === "dark") {
    aplicarTema(salvo);
  } else if (window.matchMedia("(prefers-color-scheme: dark)").matches) {
    // Só respeita o sistema enquanto o usuário nunca escolheu.
    aplicarTema("dark");
  } else {
    aplicarTema("light");
  }
}

function alternarTema() {
  const novo = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  aplicarTema(novo);
  try {
    localStorage.setItem(CHAVE_TEMA, novo);
  } catch {
    // Sem armazenamento: o tema vale só nesta visita.
  }
}

async function iniciar() {
  iniciarTema();
  $("login-form").addEventListener("submit", entrar);
  $("btn-sair").addEventListener("click", sair);
  $("btn-tema").addEventListener("click", alternarTema);
  window.addEventListener("hashchange", () => {
    if (!$("painel").hidden) ativarSecao(idInicial(), false);
  });
  try {
    const resposta = await api("/api/sessao");
    const dados = await resposta.json();
    if (dados.autenticado) mostrarPainel(dados.csrf);
    else mostrarVista("login");
  } catch {
    mostrarVista("login");
    mostrarErroLogin("Não foi possível falar com o servidor.");
  }
}

iniciar();
