// Bloco "Idiomas e queima" dentro da seção Revisão: prévia por idioma, queima, vídeo pronto
// e downloads (RF-21, RF-25, RF-26).

import { api, showToast, subscribeEvents } from "/static/app.js";
import {
  assistir,
  corteAtual,
  espacoDaQueima,
  mostrarLegenda,
  voltarAoOriginal,
} from "/static/review.js";

const SELOS = {
  traduzido: { rotulo: "Traduzido", classe: "badge-info" },
  desatualizado: { rotulo: "Desatualizado", classe: "badge-warning" },
  queimando: { rotulo: "Queimando", classe: "badge-info" },
  pronto: { rotulo: "Pronto", classe: "badge-success" },
  erro: { rotulo: "Erro", classe: "badge-danger" },
};

const DICA_TRADUZIR = "Use o caminho do pt.srt no Claude Code para traduzir";

let ui = null;
let idiomas = {};
let selecionados = new Set();
let progressoAoVivo = {}; // idioma -> { estado, progresso } vindo do SSE
let previa = null; // idioma com a prévia ativa
let assistindo = null; // idioma cujo .mp4 está no player
let queimando = false;
let carregando = false;
let carregarDeNovo = false;
let assinado = false;

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

function link(rotulo, href, nomeDoArquivo) {
  const a = el("a", "btn btn-ghost burn-link", rotulo);
  a.href = href;
  a.download = nomeDoArquivo;
  return a;
}

function url(id, caminho) {
  return `/api/cortes/${encodeURIComponent(id)}/${caminho}`;
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
  const espaco = espacoDaQueima();
  if (!espaco) return;
  const cartao = el("section", "card review-card burn-card");
  cartao.append(el("h2", "review-title", "Idiomas e queima"));
  const dica = el("p", "review-hint", DICA_TRADUZIR);
  const lista = el("ul", "burn-list");
  const erro = el("p", "form-error");
  erro.hidden = true;
  erro.setAttribute("role", "alert");
  const acoes = el("div", "review-actions");
  const btnQueimar = botao("Queimar selecionados", "btn-primary", queimar);
  const btnZip = el("a", "btn btn-ghost burn-link", "Baixar tudo (.zip)");
  acoes.append(btnQueimar, btnZip);
  cartao.append(dica, lista, erro, acoes);
  espaco.replaceChildren(cartao);
  ui = { cartao, dica, lista, erro, acoes, btnQueimar, btnZip };
}

function estadoExibido(id, dados) {
  const vivo = progressoAoVivo[id];
  if (vivo && (vivo.estado === "queimando" || vivo.estado === "aguardando")) {
    return { chave: "queimando", progresso: vivo.progresso, naFila: vivo.estado === "aguardando" };
  }
  if (dados.queima === "queimando" || dados.queima === "aguardando") {
    return { chave: "queimando", progresso: dados.progresso || 0, naFila: dados.queima === "aguardando" };
  }
  if (dados.traducao === "desatualizado" || dados.queima === "desatualizado") {
    return { chave: "desatualizado", progresso: 0 };
  }
  if (dados.queima === "erro") return { chave: "erro", progresso: 0 };
  if (dados.queima === "pronto" && dados.mp4) return { chave: "pronto", progresso: 1 };
  return { chave: "traduzido", progresso: 0 };
}

function linha(corteId, idioma, dados) {
  const exibido = estadoExibido(idioma, dados);
  const item = el("li", "burn-item");
  const topo = el("div", "burn-item-top");

  const rotuloCaixa = el("label", "burn-check");
  const caixa = document.createElement("input");
  caixa.type = "checkbox";
  caixa.checked = selecionados.has(idioma);
  caixa.disabled = dados.traducao !== "traduzido" || exibido.chave === "queimando" || queimando;
  caixa.setAttribute("aria-label", `Queimar ${idioma}`);
  caixa.addEventListener("change", () => {
    if (caixa.checked) selecionados.add(idioma);
    else selecionados.delete(idioma);
    atualizarBotoes();
  });
  rotuloCaixa.append(caixa, el("span", "burn-lang", idioma.toUpperCase()));

  const selo = SELOS[exibido.chave];
  const texto = exibido.chave === "queimando"
    ? `${exibido.naFila ? "Na fila" : "Queimando"} ${Math.round(exibido.progresso * 100)}%`
    : selo.rotulo;
  topo.append(rotuloCaixa, el("span", `badge ${selo.classe}`, texto));
  item.append(topo);

  if (exibido.chave === "queimando") {
    const trilho = el("div", "upload-track");
    const barra = el("div", "upload-bar");
    barra.style.width = `${Math.round(exibido.progresso * 100)}%`;
    trilho.append(barra);
    item.append(trilho);
  }
  if (exibido.chave === "erro" && dados.erro) {
    item.append(el("p", "form-error", dados.erro));
  }

  const botoes = el("div", "review-actions");
  const emPrevia = previa === idioma && assistindo === null;
  const btnPrevia = botao(emPrevia ? "Prévia ativa" : "Ver prévia", "btn-ghost", () =>
    verPrevia(idioma),
  );
  btnPrevia.disabled = emPrevia;
  botoes.append(btnPrevia);
  if (dados.mp4) {
    if (assistindo === idioma) {
      botoes.append(botao("Voltar ao original", "btn-ghost", () => voltar()));
    } else {
      botoes.append(botao("Assistir", "btn-ghost", () => ver(corteId, idioma)));
    }
    botoes.append(link("Baixar vídeo", `${url(corteId, `arquivos/${idioma}.mp4`)}?baixar=1`, `${corteId}-${idioma}.mp4`));
  }
  botoes.append(link("Baixar .srt", `${url(corteId, `arquivos/${idioma}.srt`)}?baixar=1`, `${corteId}-${idioma}.srt`));
  item.append(botoes);
  return item;
}

function atualizarBotoes() {
  if (!ui) return;
  const id = corteAtual();
  const temMp4 = Object.values(idiomas).some((d) => d.mp4);
  ui.btnQueimar.disabled = queimando || selecionados.size === 0;
  ui.btnQueimar.textContent = queimando ? "Enviando…" : "Queimar selecionados";
  ui.btnZip.hidden = !temMp4;
  if (temMp4 && id) {
    ui.btnZip.href = url(id, "zip");
    ui.btnZip.setAttribute("download", `${id}.zip`);
  }
}

function desenhar() {
  if (!ui) return;
  const id = corteAtual();
  const nomes = Object.keys(idiomas);
  ui.dica.hidden = nomes.length > 0;
  ui.lista.replaceChildren(...nomes.map((n) => linha(id, n, idiomas[n])));
  ui.acoes.hidden = nomes.length === 0;
  atualizarBotoes();
}

async function carregar() {
  if (!ui) return;
  if (carregando) {
    carregarDeNovo = true;
    return;
  }
  const id = corteAtual();
  if (!id) return;
  carregando = true;
  try {
    const resposta = await api(url(id, "idiomas"));
    if (resposta.ok && corteAtual() === id) {
      idiomas = await resposta.json();
      progressoAoVivo = {};
      for (const nome of [...selecionados]) {
        if (idiomas[nome]?.traducao !== "traduzido") selecionados.delete(nome);
      }
      desenhar();
    }
  } catch {
    // Sem conexão: mantém o que está na tela.
  } finally {
    carregando = false;
    if (carregarDeNovo) {
      carregarDeNovo = false;
      carregar();
    }
  }
}

function reiniciar() {
  idiomas = {};
  selecionados = new Set();
  progressoAoVivo = {};
  previa = null;
  assistindo = null;
  desenhar();
}

function verPrevia(idioma) {
  if (assistindo) voltarAoOriginal();
  assistindo = null;
  previa = idioma;
  mostrarLegenda(idioma);
  desenhar();
}

function ver(id, idioma) {
  assistindo = idioma;
  assistir(`${url(id, `arquivos/${idioma}.mp4`)}?v=${Date.now()}`);
  desenhar();
}

function voltar() {
  assistindo = null;
  previa = null;
  voltarAoOriginal();
  desenhar();
}

async function queimar() {
  const id = corteAtual();
  if (!id || !selecionados.size) return;
  ui.erro.hidden = true;
  queimando = true;
  atualizarBotoes();
  try {
    const resposta = await api(url(id, "queimar"), {
      method: "POST",
      body: { idiomas: [...selecionados] },
    });
    if (resposta.status === 202) {
      selecionados = new Set();
      showToast("Queima iniciada.", "sucesso");
    } else {
      const mensagem = await lerErro(resposta, "Não foi possível iniciar a queima.");
      ui.erro.textContent = mensagem;
      ui.erro.hidden = false;
      showToast(mensagem, resposta.status === 409 ? "aviso" : "erro");
    }
  } catch {
    showToast("Não foi possível iniciar a queima.", "erro");
  } finally {
    queimando = false;
    await carregar();
  }
}

function aoEvento(evento) {
  if (!ui || evento.clip_id !== corteAtual()) return;
  if (evento.kind === "burn" && evento.language) {
    const anterior = progressoAoVivo[evento.language];
    progressoAoVivo[evento.language] = { estado: evento.state, progresso: evento.progress || 0 };
    if (evento.state === "pronto" || evento.state === "erro") {
      if (evento.state === "erro") {
        showToast(evento.error || `A queima de ${evento.language} falhou.`, "erro");
      }
      carregar();
      return;
    }
    if (!anterior || anterior.estado !== evento.state) carregar();
    else desenhar();
    return;
  }
  carregar();
}

function recarregarSePrecisar() {
  if (ui) carregar();
}

function aoMontarRevisao() {
  montar();
  previa = null;
  assistindo = null;
  desenhar();
  carregar();
}

document.addEventListener("revisao-montada", aoMontarRevisao);

document.addEventListener("abrir-revisao", () => {
  if (!ui) aoMontarRevisao();
  reiniciar();
  carregar();
});

document.addEventListener("secao-ativada", (evento) => {
  if (evento.detail?.id === "revisao") recarregarSePrecisar();
});

if (espacoDaQueima()) aoMontarRevisao();

if (!assinado) {
  assinado = true;
  subscribeEvents(aoEvento);
}
