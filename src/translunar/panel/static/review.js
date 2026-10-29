// Seção "Revisão": prévia com a legenda pt-BR, editor do pt.srt, contexto e transcrição.

import { api, registerSection, showToast, subscribeEvents } from "/static/app.js";

const ICONE_REVISAO =
  '<path d="M4 5h16a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1h-8l-5 4v-4H4a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1z"/>' +
  '<path d="M7 9.5h10M7 12.5h6"/>';

// Mesma proporção da queima: tamanho da fonte = 5,8% da largura do vídeo (RN-08). O libass mede
// o Fontsize pela altura ascendente + descendente da fonte, não pelo em do CSS: na Inter, essa
// altura é (1984 + 494) / 2048 do em. Sem a conversão, a prévia fica 21% maior que a queima e
// quebra em 3 linhas legendas que saem em 2 no vídeo.
const ALTURA_LIBASS_EM = (1984 + 494) / 2048;
const PROPORCAO_FONTE = 0.058 / ALTURA_LIBASS_EM;

let raiz = null;
let corteId = null;
let corte = null;
let pontoDeObservacao = null;
let assinado = false;
let idiomaDaFaixa = "pt";
const ui = {};

function el(tag, classe, texto) {
  const no = document.createElement(tag);
  if (classe) no.className = classe;
  if (texto !== undefined) no.textContent = texto;
  return no;
}

function botao(rotulo, classe, aoClicar) {
  const b = el("button", `btn ${classe}`, rotulo);
  b.type = "button";
  b.addEventListener("click", aoClicar);
  return b;
}

async function lerErro(resposta, padrao) {
  try {
    const dados = await resposta.json();
    return dados.detail || padrao;
  } catch {
    return padrao;
  }
}

function montar() {
  const vazio = el("p", "empty-state", "Escolha um corte no Acervo.");
  const conteudo = el("div", "review");
  conteudo.hidden = true;

  // Coluna do player
  const colPlayer = el("div", "review-player card");
  const moldura = el("div", "review-frame");
  const video = document.createElement("video");
  video.controls = true;
  video.playsInline = true;
  video.className = "review-video";
  const faixa = document.createElement("track");
  faixa.kind = "subtitles";
  faixa.srclang = "pt";
  faixa.label = "Português";
  faixa.default = true;
  video.append(faixa);
  moldura.append(video);
  const semLegenda = el(
    "p",
    "review-note",
    "Ainda não há legenda. Transcreva o corte para ver a prévia.",
  );
  colPlayer.append(moldura, semLegenda);

  // Coluna do editor
  const colEditor = el("div", "review-side");

  const cartaoTranscricao = el("section", "card review-card");
  cartaoTranscricao.append(el("h2", "review-title", "Transcrição"));
  const estado = el("p", "review-state");
  const trilho = el("div", "upload-track");
  const barra = el("div", "upload-bar");
  barra.style.width = "0%";
  trilho.append(barra);
  trilho.hidden = true;
  const erro = el("p", "form-error");
  erro.hidden = true;
  const acoes = el("div", "review-actions");
  const btnTranscrever = botao("Transcrever", "btn-primary", () => transcrever(false));
  const btnRefazer = botao("Refazer transcrição", "btn-ghost", () => {
    const ok = window.confirm(
      "Refazer a transcrição sobrescreve o pt.srt, inclusive as suas edições. Continuar?",
    );
    if (ok) transcrever(true);
  });
  acoes.append(btnTranscrever, btnRefazer);
  cartaoTranscricao.append(estado, trilho, erro, acoes);

  const cartaoCaminho = el("section", "card review-card");
  cartaoCaminho.append(el("h2", "review-title", "Caminho do pt.srt"));
  const linhaCaminho = el("div", "review-path-row");
  const caminho = document.createElement("input");
  caminho.type = "text";
  caminho.readOnly = true;
  caminho.className = "review-input review-mono";
  caminho.setAttribute("aria-label", "Caminho do pt.srt");
  const btnCopiar = botao("Copiar", "btn-ghost", copiarCaminho);
  linhaCaminho.append(caminho, btnCopiar);
  cartaoCaminho.append(
    linhaCaminho,
    el("p", "review-hint", "Cole este caminho no Claude Code para traduzir"),
  );

  const cartaoEditor = el("section", "card review-card");
  cartaoEditor.append(el("h2", "review-title", "Legenda em português (pt.srt)"));
  const editor = document.createElement("textarea");
  editor.className = "review-input review-mono review-editor";
  editor.spellcheck = false;
  editor.setAttribute("aria-label", "Conteúdo do pt.srt");
  const erroSrt = el("p", "form-error");
  erroSrt.hidden = true;
  erroSrt.setAttribute("role", "alert");
  const btnSalvar = botao("Salvar", "btn-primary", salvarSrt);
  const acoesEditor = el("div", "review-actions");
  acoesEditor.append(btnSalvar);
  cartaoEditor.append(editor, erroSrt, acoesEditor);

  const cartaoContexto = el("section", "card review-card");
  cartaoContexto.append(el("h2", "review-title", "Contexto do vídeo"));
  const contexto = document.createElement("textarea");
  contexto.className = "review-input review-context";
  contexto.setAttribute("aria-label", "Contexto do vídeo");
  contexto.placeholder = "Assunto, tom e termos que ajudam a traduzir.";
  const btnContexto = botao("Salvar contexto", "btn-ghost", salvarContexto);
  const acoesContexto = el("div", "review-actions");
  acoesContexto.append(btnContexto);
  cartaoContexto.append(contexto, acoesContexto);

  // Espaço do bloco "Idiomas e queima" (burn.js), entre o caminho do pt.srt e o editor.
  const espacoQueima = el("div", "review-burn-slot");

  colEditor.append(cartaoTranscricao, cartaoCaminho, espacoQueima, cartaoEditor, cartaoContexto);
  conteudo.append(colPlayer, colEditor);

  Object.assign(ui, {
    vazio, conteudo, espacoQueima, video, faixa, moldura, semLegenda, estado, trilho, barra, erro,
    btnTranscrever, btnRefazer, caminho, btnCopiar, editor, erroSrt, btnSalvar,
    contexto, btnContexto,
  });
  return [vazio, conteudo];
}

function ajustarLegenda() {
  const { video, moldura } = ui;
  if (!video || !video.isConnected) return;
  const razao = video.videoWidth && video.videoHeight ? video.videoWidth / video.videoHeight : null;
  let largura = video.clientWidth;
  if (razao) largura = Math.min(video.clientWidth, video.clientHeight * razao);
  moldura.style.setProperty("--cue-size", `${(largura * PROPORCAO_FONTE).toFixed(2)}px`);
}

function observarVideo() {
  if (pontoDeObservacao) pontoDeObservacao.disconnect();
  pontoDeObservacao = new ResizeObserver(ajustarLegenda);
  pontoDeObservacao.observe(ui.video);
  ui.video.addEventListener("loadedmetadata", ajustarLegenda);
}

const NOMES_IDIOMA = { pt: "Português" };

// Troca a faixa de legenda do player para o idioma (a mesma prévia e o mesmo tamanho do pt-BR).
export function mostrarLegenda(idioma = "pt") {
  if (!raiz || !corteId) return;
  idiomaDaFaixa = idioma;
  ui.faixa.srclang = idioma;
  ui.faixa.label = NOMES_IDIOMA[idioma] || idioma;
  ui.faixa.src = `/api/cortes/${encodeURIComponent(corteId)}/legendas/${encodeURIComponent(idioma)}.vtt?v=${Date.now()}`;
  // Reativa a faixa para o navegador buscar de novo o arquivo.
  const faixaTexto = ui.video.textTracks[0];
  if (faixaTexto) faixaTexto.mode = "showing";
}

function recarregarFaixa() {
  mostrarLegenda("pt");
}

// Troca o vídeo do player pelo arquivo já queimado; a faixa sai, pois a legenda está no vídeo.
export function assistir(url) {
  if (!raiz || !ui.video) return;
  const faixaTexto = ui.video.textTracks[0];
  if (faixaTexto) faixaTexto.mode = "disabled";
  ui.video.src = url;
  ui.video.play().catch(() => {});
}

// Volta ao vídeo original com a legenda pt-BR.
export function voltarAoOriginal() {
  if (!raiz || !corteId) return;
  ui.video.src = `/api/cortes/${encodeURIComponent(corteId)}/video`;
  mostrarLegenda("pt");
}

export function corteAtual() {
  return corteId;
}

export function espacoDaQueima() {
  return raiz ? ui.espacoQueima : null;
}

export function idiomaDaFaixaAtual() {
  return idiomaDaFaixa;
}

function descreverEstado(c) {
  const t = c.estado?.transcription;
  const estado = t?.state || "aguardando";
  const rotulos = {
    aguardando: "Ainda não transcrito.",
    transcrevendo: "Transcrevendo…",
    transcrito: "Transcrição concluída.",
    erro: "A transcrição falhou.",
    interrompido: "A transcrição foi interrompida. Transcreva de novo.",
  };
  return rotulos[estado] || estado;
}

function atualizarAcoes() {
  const temSrt = Boolean(corte?.pt_srt);
  const ocupado = Boolean(corte?.em_processamento);
  ui.btnTranscrever.hidden = temSrt;
  ui.btnRefazer.hidden = !temSrt;
  ui.btnTranscrever.disabled = ocupado;
  ui.btnRefazer.disabled = ocupado;
  ui.btnSalvar.disabled = ocupado || !temSrt;
  ui.editor.disabled = !temSrt;
  ui.semLegenda.hidden = temSrt;
  ui.caminho.value = corte?.pt_srt || "";
  ui.btnCopiar.disabled = !temSrt;
  ui.estado.textContent = descreverEstado(corte || {});
}

async function buscarCorte(id) {
  const resposta = await api("/api/cortes");
  if (!resposta.ok) return null;
  const lista = await resposta.json();
  return lista.find((item) => item.id === id) || null;
}

async function carregarTexto() {
  ui.erroSrt.hidden = true;
  if (corte?.pt_srt) {
    const r = await api(`/api/cortes/${encodeURIComponent(corteId)}/pt-srt`);
    ui.editor.value = r.ok ? await r.text() : "";
    recarregarFaixa();
  } else {
    ui.editor.value = "";
    ui.faixa.removeAttribute("src");
  }
  const c = await api(`/api/cortes/${encodeURIComponent(corteId)}/contexto`);
  ui.contexto.value = c.ok ? await c.text() : "";
}

async function abrir(id) {
  corteId = id;
  corte = null;
  if (!raiz) return;
  ui.vazio.hidden = true;
  ui.conteudo.hidden = false;
  ui.erro.hidden = true;
  ui.trilho.hidden = true;
  ui.video.src = `/api/cortes/${encodeURIComponent(id)}/video`;
  idiomaDaFaixa = "pt";
  observarVideo();
  try {
    corte = await buscarCorte(id);
    if (!corte) {
      showToast("Corte não encontrado.", "erro");
      return;
    }
    atualizarAcoes();
    await carregarTexto();
  } catch {
    showToast("Não foi possível carregar o corte.", "erro");
  }
}

async function transcrever(forcar) {
  ui.erro.hidden = true;
  const resposta = await api(`/api/cortes/${encodeURIComponent(corteId)}/transcrever`, {
    method: "POST",
    body: { forcar },
  });
  if (resposta.status === 202) {
    ui.btnTranscrever.disabled = true;
    ui.btnRefazer.disabled = true;
    ui.estado.textContent = "Aguardando a fila…";
    ui.trilho.hidden = false;
    ui.barra.style.width = "0%";
  } else if (resposta.status === 409) {
    showToast("O corte já está em processamento.", "aviso");
  } else {
    showToast(await lerErro(resposta, "Não foi possível iniciar a transcrição."), "erro");
  }
}

async function salvarSrt() {
  ui.erroSrt.hidden = true;
  const resposta = await api(`/api/cortes/${encodeURIComponent(corteId)}/pt-srt`, {
    method: "PUT",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
    body: ui.editor.value,
  });
  if (resposta.ok) {
    showToast("Legenda salva.", "sucesso");
    recarregarFaixa();
  } else if (resposta.status === 422) {
    const dados = await resposta.json().catch(() => ({}));
    ui.erroSrt.textContent = dados.detail || "Formato de legenda inválido.";
    ui.erroSrt.hidden = false;
  } else {
    showToast(await lerErro(resposta, "Não foi possível salvar a legenda."), "erro");
  }
}

async function salvarContexto() {
  const resposta = await api(`/api/cortes/${encodeURIComponent(corteId)}/contexto`, {
    method: "PUT",
    headers: { "Content-Type": "text/plain; charset=utf-8" },
    body: ui.contexto.value,
  });
  if (resposta.ok) showToast("Contexto salvo.", "sucesso");
  else showToast(await lerErro(resposta, "Não foi possível salvar o contexto."), "erro");
}

async function copiarCaminho() {
  const texto = ui.caminho.value;
  try {
    await navigator.clipboard.writeText(texto);
    showToast("Caminho copiado.", "sucesso");
  } catch {
    ui.caminho.focus();
    ui.caminho.select();
    showToast("Selecionei o caminho: copie com Ctrl+C.", "aviso");
  }
}

function aoEvento(evento) {
  if (!raiz || evento.clip_id !== corteId || evento.kind !== "transcription") return;
  if (evento.state === "erro") {
    ui.trilho.hidden = true;
    ui.erro.textContent = evento.error || "A transcrição falhou.";
    ui.erro.hidden = false;
  } else if (evento.state === "transcrito") {
    ui.trilho.hidden = true;
  } else {
    ui.trilho.hidden = false;
    ui.barra.style.width = `${Math.round((evento.progress || 0) * 100)}%`;
    ui.estado.textContent =
      evento.state === "transcrevendo"
        ? `Transcrevendo… ${Math.round((evento.progress || 0) * 100)}%`
        : "Aguardando a fila…";
    return;
  }
  // Fim do job (sucesso ou erro): relê o corte e o texto.
  buscarCorte(corteId)
    .then((atual) => {
      corte = atual;
      atualizarAcoes();
      return carregarTexto();
    })
    .catch(() => {});
}

function renderizar(secao) {
  raiz = secao;
  secao.replaceChildren(...montar());
  document.dispatchEvent(new CustomEvent("revisao-montada"));
  if (corteId) abrir(corteId);
  if (!assinado) {
    assinado = true;
    subscribeEvents(aoEvento);
  }
}

function fechar() {
  corteId = null;
  corte = null;
  ui.video.removeAttribute("src");
  ui.video.load();
  ui.conteudo.hidden = true;
  ui.vazio.hidden = false;
}

// Ao voltar para a revisão, confere se o corte ainda existe e se o estado mudou, sem descartar
// uma edição não salva: o texto só é recarregado quando o pt.srt apareceu ou sumiu.
async function atualizarCorte() {
  try {
    const atual = await buscarCorte(corteId);
    if (!atual) {
      fechar();
      return;
    }
    const mudouSrt = Boolean(atual.pt_srt) !== Boolean(corte?.pt_srt);
    corte = atual;
    atualizarAcoes();
    if (mudouSrt) await carregarTexto();
  } catch {
    // Sem conexão: mantém o que está na tela.
  }
}

document.addEventListener("secao-ativada", (evento) => {
  if (evento.detail?.id === "revisao" && raiz && corteId) atualizarCorte();
});

document.addEventListener("abrir-revisao", (evento) => {
  const id = evento.detail?.id;
  if (id) abrir(id);
});

registerSection("revisao", renderizar, {
  label: "Revisão",
  icon: ICONE_REVISAO,
  subtitle: "Confira e ajuste a legenda em pt-BR.",
});
