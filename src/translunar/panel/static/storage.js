// Seção "Armazenamento": uso do disco, seleção de cortes e exclusão definitiva (RF-27 a RF-29).

import { api, registerSection, showToast, subscribeEvents } from "/static/app.js";

const ICONE_DISCO =
  '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/>' +
  '<path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>';

// Cada corte vira até dois itens na lista: o vídeo original (com o contexto) e as saídas
// (legendas, prévias e vídeos queimados). O filtro escolhe quais itens aparecem; a exclusão
// apaga exatamente os itens marcados.
const TIPOS = {
  original: { rotulo: "Vídeo original", descricao: "vídeo(s) original(is) com o contexto" },
  saidas: { rotulo: "Legendas e queimas", descricao: "saída(s): legendas, prévias e queimas" },
};

const VISOES = [
  { id: "tudo", rotulo: "Tudo" },
  { id: "original", rotulo: "Vídeos originais" },
  { id: "saidas", rotulo: "Legendas e queimas" },
];

const MS_POR_DIA = 24 * 60 * 60 * 1000;

let raiz = null;
let areaDisco = null;
let areaLista = null;
let barra = null;
let dialogo = null;
let cortes = [];
let selecionados = new Set();
let visao = "tudo";
let excluindo = false;
let assinado = false;
let carregando = false;
let carregarDeNovo = false;

function el(tag, classe, texto) {
  const no = document.createElement(tag);
  if (classe) no.className = classe;
  if (texto !== undefined) no.textContent = texto;
  return no;
}

export function formatarBytes(bytes) {
  const valor = Math.max(0, Number(bytes) || 0);
  if (valor >= 1024 ** 3) return `${(valor / 1024 ** 3).toFixed(1)} GB`;
  if (valor >= 1024 ** 2) return `${(valor / 1024 ** 2).toFixed(valor < 10 * 1024 ** 2 ? 1 : 0)} MB`;
  if (valor >= 1024) return `${Math.round(valor / 1024)} KB`;
  return `${valor} B`;
}

function formatarData(iso) {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "-";
  return data.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" });
}

function chave(corte, tipo) {
  return `${tipo}:${corte.id}`;
}

function itensDoCorte(corte) {
  const itens = [];
  if (visao !== "saidas") {
    itens.push({ corte, tipo: "original", tamanho: corte.tamanho_bytes });
  }
  if (visao !== "original") {
    const tamanho = Math.max(0, corte.tamanho_total_bytes - corte.tamanho_bytes);
    itens.push({ corte, tipo: "saidas", tamanho });
  }
  return itens;
}

function itensVisiveis() {
  return cortes.flatMap(itensDoCorte);
}

function selecionaveis() {
  return itensVisiveis().filter((item) => !item.corte.em_processamento);
}

function itensSelecionados() {
  return itensVisiveis().filter((item) => selecionados.has(chave(item.corte, item.tipo)));
}

function estimativa() {
  return itensSelecionados().reduce((soma, item) => soma + item.tamanho, 0);
}

function descricaoDaSelecao() {
  const contagem = { original: 0, saidas: 0 };
  for (const item of itensSelecionados()) contagem[item.tipo] += 1;
  return Object.entries(contagem)
    .filter(([, n]) => n > 0)
    .map(([tipo, n]) => `${n} ${TIPOS[tipo].descricao}`)
    .join(" e ");
}

function segmento(classe, percentual, titulo) {
  const parte = el("span", `disk-seg ${classe}`);
  parte.style.width = `${Math.max(0, Math.min(100, percentual))}%`;
  parte.title = titulo;
  return parte;
}

function legenda(classe, rotulo, valor) {
  const item = el("li", "disk-legend-item");
  item.append(el("span", `disk-dot ${classe}`), el("span", "disk-legend-label", rotulo));
  item.append(el("strong", "disk-legend-value", valor));
  return item;
}

function renderizarDisco(disco) {
  const total = disco.total_bytes || 1;
  const dados = Math.min(disco.dados_bytes, disco.usado_bytes);
  const outros = Math.max(0, disco.usado_bytes - dados);
  const trilho = el("div", "disk-track");
  trilho.setAttribute("role", "img");
  trilho.setAttribute(
    "aria-label",
    `${formatarBytes(disco.usado_bytes)} usados de ${formatarBytes(disco.total_bytes)}`,
  );
  trilho.append(
    segmento("disk-seg-app", (dados / total) * 100, `Translunar: ${formatarBytes(dados)}`),
    segmento("disk-seg-other", (outros / total) * 100, `Outros usos: ${formatarBytes(outros)}`),
  );
  const itens = el("ul", "disk-legend");
  itens.append(
    legenda("disk-seg-app", "Translunar", formatarBytes(dados)),
    legenda("disk-seg-other", "Outros usos", formatarBytes(outros)),
    legenda("disk-seg-free", "Livre", formatarBytes(disco.livre_bytes)),
  );
  const titulo = el(
    "p",
    "disk-summary",
    `${formatarBytes(disco.livre_bytes)} livres de ${formatarBytes(disco.total_bytes)}`,
  );
  areaDisco.replaceChildren(titulo, trilho, itens);
}

async function carregarDisco() {
  try {
    const resposta = await api("/api/disco");
    if (resposta.ok) renderizarDisco(await resposta.json());
    else if (resposta.status !== 401) showToast("Não foi possível ler o espaço em disco.", "erro");
  } catch {
    showToast("Não foi possível falar com o servidor.", "erro");
  }
}

function atualizarBarra() {
  const quantidade = selecionados.size;
  barra.excluir.disabled = excluindo || quantidade === 0;
  barra.excluir.textContent = quantidade
    ? `Excluir selecionados (${quantidade})`
    : "Excluir selecionados";
  const aptos = selecionaveis();
  barra.todos.checked =
    aptos.length > 0 && aptos.every((item) => selecionados.has(chave(item.corte, item.tipo)));
  barra.todos.disabled = aptos.length === 0 || excluindo;
  barra.resumo.textContent = quantidade
    ? `${quantidade} selecionado(s), cerca de ${formatarBytes(estimativa())} a liberar`
    : "Nada selecionado";
}

function linhaDoItem(item) {
  const { corte, tipo } = item;
  const linha = el("li", "storage-row");
  linha.dataset.clipId = corte.id;
  linha.dataset.tipo = tipo;
  const caixa = el("input");
  caixa.type = "checkbox";
  caixa.className = "storage-check";
  caixa.checked = selecionados.has(chave(corte, tipo));
  caixa.disabled = corte.em_processamento || excluindo;
  caixa.setAttribute("aria-label", `Selecionar ${TIPOS[tipo].rotulo} de ${corte.video}`);
  caixa.addEventListener("change", () => {
    if (caixa.checked) selecionados.add(chave(corte, tipo));
    else selecionados.delete(chave(corte, tipo));
    atualizarBarra();
  });
  const nome = el("span", "storage-name", corte.video);
  nome.title = corte.video;
  linha.append(caixa, nome);
  if (corte.em_processamento) linha.append(el("span", "badge badge-info", "Em processamento"));
  else linha.append(el("span", `badge storage-kind storage-kind-${tipo}`, TIPOS[tipo].rotulo));
  linha.append(
    el("span", "storage-date", formatarData(corte.modificado_em)),
    el("span", "storage-size", formatarBytes(item.tamanho)),
  );
  if (corte.em_processamento) linha.classList.add("storage-row-busy");
  return linha;
}

function renderizarLista() {
  areaLista.replaceChildren();
  if (!cortes.length) {
    areaLista.append(el("p", "empty-state", "Nenhum corte para limpar."));
    atualizarBarra();
    return;
  }
  const lista = el("ul", "storage-list");
  lista.append(...itensVisiveis().map(linhaDoItem));
  areaLista.append(lista);
  atualizarBarra();
}

async function carregarCortes() {
  if (carregando) {
    carregarDeNovo = true;
    return;
  }
  carregando = true;
  try {
    const resposta = await api("/api/cortes");
    if (resposta.ok) {
      cortes = await resposta.json();
      const aptos = new Set(selecionaveis().map((item) => chave(item.corte, item.tipo)));
      selecionados = new Set([...selecionados].filter((id) => aptos.has(id)));
      renderizarLista();
    } else if (resposta.status !== 401) {
      showToast("Não foi possível carregar os cortes.", "erro");
    }
  } catch {
    showToast("Não foi possível falar com o servidor.", "erro");
  } finally {
    carregando = false;
    if (carregarDeNovo) {
      carregarDeNovo = false;
      carregarCortes();
    }
  }
}

function recarregar() {
  carregarDisco();
  carregarCortes();
}

function selecionarPorIdade() {
  const dias = Number(barra.dias.value);
  if (!Number.isFinite(dias) || dias < 0 || barra.dias.value === "") {
    showToast("Informe a quantidade de dias.", "aviso");
    return;
  }
  const limite = Date.now() - dias * MS_POR_DIA;
  selecionados = new Set(
    selecionaveis()
      .filter((item) => new Date(item.corte.modificado_em).getTime() < limite)
      .map((item) => chave(item.corte, item.tipo)),
  );
  if (!selecionados.size) showToast(`Nada com mais de ${dias} dia(s).`, "aviso");
  renderizarLista();
}

function pedirConfirmacao() {
  const texto = dialogo.querySelector(".confirm-text");
  texto.replaceChildren(
    el("p", "", `Excluir ${descricaoDaSelecao()}.`),
    el("p", "", `Espaço estimado a liberar: ${formatarBytes(estimativa())}.`),
    el("p", "confirm-warning", "A exclusão é definitiva: não há lixeira."),
  );
  dialogo.showModal();
}

async function excluirSelecionados() {
  // Os dois itens de um mesmo corte marcados viram uma exclusão só, com alvo=tudo.
  const porCorte = new Map();
  for (const item of itensSelecionados()) {
    const tipos = porCorte.get(item.corte.id) || new Set();
    tipos.add(item.tipo);
    porCorte.set(item.corte.id, tipos);
  }
  excluindo = true;
  atualizarBarra();
  let liberado = 0;
  let apagados = 0;
  let emProcessamento = 0;
  let falhas = 0;
  for (const [id, tipos] of porCorte) {
    const alvo = tipos.size === 2 ? "tudo" : [...tipos][0];
    try {
      const resposta = await api(
        `/api/cortes/${encodeURIComponent(id)}?alvo=${encodeURIComponent(alvo)}`,
        { method: "DELETE" },
      );
      if (resposta.ok) {
        liberado += (await resposta.json()).liberado_bytes || 0;
        apagados += 1;
      } else if (resposta.status === 409) {
        emProcessamento += 1;
      } else if (resposta.status !== 404) {
        falhas += 1;
      }
    } catch {
      falhas += 1;
    }
  }
  excluindo = false;
  selecionados = new Set();
  if (apagados) showToast(`${formatarBytes(liberado)} liberados (${apagados} corte(s)).`, "sucesso");
  if (emProcessamento) showToast(`${emProcessamento} corte(s): corte em processamento.`, "aviso");
  if (falhas) showToast(`${falhas} corte(s) não puderam ser excluídos.`, "erro");
  recarregar();
}

function montarBarra() {
  const caixaTodos = el("input");
  caixaTodos.type = "checkbox";
  caixaTodos.setAttribute("aria-label", "Selecionar tudo o que está visível");
  caixaTodos.addEventListener("change", () => {
    selecionados = caixaTodos.checked
      ? new Set(selecionaveis().map((item) => chave(item.corte, item.tipo)))
      : new Set();
    renderizarLista();
  });
  const rotuloTodos = el("label", "storage-all");
  rotuloTodos.append(caixaTodos, el("span", "", "Todos"));

  const dias = el("input");
  dias.type = "number";
  dias.min = "0";
  dias.step = "1";
  dias.value = "30";
  dias.className = "storage-days";
  dias.setAttribute("aria-label", "Dias");
  const filtrar = el("button", "btn btn-ghost", "Selecionar");
  filtrar.type = "button";
  filtrar.addEventListener("click", selecionarPorIdade);
  const filtro = el("div", "storage-filter");
  filtro.append(el("span", "", "Mais antigos que"), dias, el("span", "", "dias"), filtrar);

  const grupo = el("div", "segmented");
  grupo.setAttribute("role", "group");
  grupo.setAttribute("aria-label", "O que mostrar");
  for (const opcao of VISOES) {
    const botao = el("button", "segmented-item", opcao.rotulo);
    botao.type = "button";
    botao.setAttribute("aria-pressed", String(opcao.id === visao));
    botao.addEventListener("click", () => {
      visao = opcao.id;
      for (const outro of grupo.children) {
        outro.setAttribute("aria-pressed", String(outro === botao));
      }
      // Só fica marcado o que continua visível: a exclusão nunca apaga algo escondido.
      const visiveis = new Set(itensVisiveis().map((item) => chave(item.corte, item.tipo)));
      selecionados = new Set([...selecionados].filter((k) => visiveis.has(k)));
      renderizarLista();
    });
    grupo.append(botao);
  }

  const excluir = el("button", "btn btn-danger", "Excluir selecionados");
  excluir.type = "button";
  excluir.addEventListener("click", () => {
    if (selecionados.size && !excluindo) pedirConfirmacao();
  });
  const resumo = el("p", "storage-summary");
  resumo.setAttribute("aria-live", "polite");

  const acoes = el("div", "storage-actions");
  acoes.append(grupo, filtro, excluir);
  const topo = el("div", "storage-toolbar");
  topo.append(rotuloTodos, resumo);
  const conjunto = el("div", "storage-controls");
  conjunto.append(acoes, topo);
  barra = { dias, excluir, resumo, todos: caixaTodos };
  return conjunto;
}

function montarDialogo() {
  const caixa = el("dialog", "confirm-dialog");
  caixa.setAttribute("aria-labelledby", "confirm-titulo");
  const titulo = el("h2", "confirm-title", "Confirmar exclusão");
  titulo.id = "confirm-titulo";
  const texto = el("div", "confirm-text");
  const cancelar = el("button", "btn btn-ghost", "Cancelar");
  cancelar.type = "button";
  cancelar.addEventListener("click", () => caixa.close());
  const confirmar = el("button", "btn btn-danger", "Excluir definitivamente");
  confirmar.type = "button";
  confirmar.addEventListener("click", () => {
    caixa.close();
    excluirSelecionados();
  });
  const acoes = el("div", "confirm-actions");
  acoes.append(cancelar, confirmar);
  caixa.append(titulo, texto, acoes);
  return caixa;
}

function renderizar(secao) {
  raiz = secao;
  areaDisco = el("div", "disk-card");
  areaLista = el("div", "storage-body");
  dialogo = montarDialogo();
  secao.replaceChildren(areaDisco, montarBarra(), areaLista, dialogo);
  atualizarBarra();
  recarregar();
  if (!assinado) {
    assinado = true;
    // Um corte que começa ou termina de processar muda a seleção possível.
    subscribeEvents(() => {
      if (raiz && !raiz.hidden && !excluindo) carregarCortes();
    });
  }
}

document.addEventListener("secao-ativada", (evento) => {
  if (evento.detail?.id === "armazenamento" && raiz && !excluindo) recarregar();
});

registerSection("armazenamento", renderizar, {
  label: "Armazenamento",
  icon: ICONE_DISCO,
  subtitle: "Espaço em disco e limpeza de cortes.",
});
