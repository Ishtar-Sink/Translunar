// Seção "Acervo": envio de cortes (arrastar e soltar) e lista dos cortes em entrada/.

import { api, registerSection, showSection, showToast, subscribeEvents } from "/static/app.js";

const ICONE_ACERVO =
  '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M3 11h18"/>' +
  '<path d="M7 7l2.5-4M13 7l2.5-4M7 3.5L5 7"/>';

// Formato de exibição escolhido por corte, guardado só neste navegador.
const PREFIXO_FORMATO = "translunar-formato-";
const FORMATOS = [
  { id: "9x16", rotulo: "9:16" },
  { id: "16x9", rotulo: "16:9" },
];

const TONS_ESTADO = {
  pronto: "success",
  traduzido: "success",
  transcrito: "success",
  transcrevendo: "info",
  queimando: "info",
  desatualizado: "warning",
  interrompido: "warning",
  erro: "danger",
  aguardando: "muted",
};

const MENSAGENS_ERRO = {
  400: "Formato não suportado ou envio inválido.",
  411: "O navegador não informou o tamanho do arquivo.",
  413: "Arquivo acima do limite de tamanho do servidor.",
  507: "Sem espaço livre no servidor para este arquivo.",
};

let raiz = null;
let areaLista = null;
let areaEnvios = null;
let fila = Promise.resolve();
let assinado = false;
let recarregando = false;
let recarregarDeNovo = false;

function el(tag, classe, texto) {
  const no = document.createElement(tag);
  if (classe) no.className = classe;
  if (texto !== undefined) no.textContent = texto;
  return no;
}

export function formatarDuracao(segundos) {
  if (segundos == null) return "--:--";
  const total = Math.round(segundos);
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(total % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

export function formatarTamanho(bytes) {
  const mb = bytes / (1024 * 1024);
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(mb < 10 ? 1 : 0)} MB`;
}

function selo(rotulo, estado) {
  const tom = TONS_ESTADO[estado] || "muted";
  return el("span", `badge badge-${tom}`, rotulo);
}

function selosDoCorte(corte) {
  const estado = corte.estado || {};
  const selos = [];
  const transcricao = estado.transcription?.state || "aguardando";
  selos.push(selo(`Transcrição: ${transcricao}`, transcricao));
  for (const [idioma, traducao] of Object.entries(estado.translations || {})) {
    selos.push(selo(`${idioma.toUpperCase()}: ${traducao.state}`, traducao.state));
  }
  for (const [idioma, queima] of Object.entries(estado.burns || {})) {
    selos.push(selo(`Queima ${idioma.toUpperCase()}: ${queima.state}`, queima.state));
  }
  return selos;
}

function formatoNativo(corte) {
  if (!corte.largura || !corte.altura) return null;
  return corte.largura > corte.altura ? "16x9" : "9x16";
}

function formatoDoCorte(corte) {
  try {
    const salvo = localStorage.getItem(PREFIXO_FORMATO + corte.id);
    if (FORMATOS.some((formato) => formato.id === salvo)) return salvo;
  } catch {
    // Sem armazenamento: usa o formato do próprio vídeo.
  }
  return formatoNativo(corte) || "9x16";
}

function rotuloDoFormato(id) {
  return FORMATOS.find((formato) => formato.id === id).rotulo;
}

// O aviso só aparece quando o formato escolhido diverge do formato do vídeo.
function avisoDeFormato(corte, formato) {
  const nativo = formatoNativo(corte);
  if (!nativo || nativo === formato) return null;
  return `Vídeo em ${rotuloDoFormato(nativo)}: bordas cortadas`;
}

function aplicarFormato(cartao, corte, formato) {
  cartao.classList.toggle("clip-card-16x9", formato === "16x9");
  for (const botao of cartao.querySelectorAll(".segmented-item")) {
    botao.setAttribute("aria-pressed", String(botao.dataset.formato === formato));
  }
  const aviso = cartao.querySelector(".clip-alert-formato");
  const texto = avisoDeFormato(corte, formato);
  aviso.textContent = texto || "";
  aviso.hidden = !texto;
}

function seletorDeFormato(cartao, corte) {
  const grupo = el("div", "segmented");
  grupo.setAttribute("role", "group");
  grupo.setAttribute("aria-label", `Formato de ${corte.video}`);
  for (const formato of FORMATOS) {
    const botao = el("button", "segmented-item", formato.rotulo);
    botao.type = "button";
    botao.dataset.formato = formato.id;
    botao.addEventListener("click", () => {
      try {
        localStorage.setItem(PREFIXO_FORMATO + corte.id, formato.id);
      } catch {
        // Sem armazenamento: o formato vale só até recarregar a lista.
      }
      aplicarFormato(cartao, corte, formato.id);
    });
    grupo.append(botao);
  }
  return grupo;
}

function cartaoDoCorte(corte) {
  const cartao = el("article", "clip-card");
  cartao.dataset.clipId = corte.id;

  const quadro = el("div", "clip-thumb");
  if (corte.miniatura) {
    const img = el("img");
    img.src = corte.miniatura;
    img.alt = `Miniatura de ${corte.video}`;
    img.loading = "lazy";
    const moldura = el("div", "clip-frame");
    moldura.append(img);
    quadro.append(moldura);
  } else {
    quadro.append(el("span", "clip-thumb-vazia", "Sem miniatura"));
  }
  if (corte.em_processamento) quadro.append(el("span", "clip-busy", "Em processamento"));
  cartao.append(quadro);

  const corpo = el("div", "clip-body");
  const titulo = el("h3", "clip-name", corte.video);
  titulo.title = corte.video;
  corpo.append(titulo);
  const linha = el("div", "clip-meta-row");
  linha.append(
    el("p", "clip-meta", `${formatarDuracao(corte.duracao_s)} · ${formatarTamanho(corte.tamanho_bytes)}`),
  );
  if (formatoNativo(corte)) linha.append(seletorDeFormato(cartao, corte));
  corpo.append(linha);
  if (corte.erro) corpo.append(el("p", "clip-alert clip-alert-danger", corte.erro));
  const aviso = el("p", "clip-alert clip-alert-warning clip-alert-formato");
  aviso.hidden = true;
  corpo.append(aviso);
  const selos = el("div", "clip-badges");
  selos.append(...selosDoCorte(corte));
  corpo.append(selos);

  // Sem pt.srt o botão convida a transcrever; os dois abrem a revisão, onde fica o disparo.
  const abrir = el("button", "btn btn-ghost clip-open", corte.pt_srt ? "Abrir" : "Transcrever");
  abrir.type = "button";
  abrir.dataset.clipId = corte.id;
  abrir.addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("abrir-revisao", { detail: { id: corte.id } }));
    showSection("revisao");
  });
  corpo.append(abrir);
  cartao.append(corpo);
  aplicarFormato(cartao, corte, formatoDoCorte(corte));
  return cartao;
}

function renderizarLista(cortes) {
  areaLista.replaceChildren();
  if (!cortes.length) {
    areaLista.append(
      el("p", "empty-state", "Nenhum corte ainda. Envie um vídeo acima para começar."),
    );
    return;
  }
  const grade = el("div", "clip-grid");
  grade.append(...cortes.map(cartaoDoCorte));
  areaLista.append(grade);
}

async function carregarLista() {
  if (recarregando) {
    recarregarDeNovo = true;
    return;
  }
  recarregando = true;
  try {
    const resposta = await api("/api/cortes");
    if (resposta.ok) renderizarLista(await resposta.json());
    else if (resposta.status !== 401) showToast("Não foi possível carregar o acervo.", "erro");
  } catch {
    showToast("Não foi possível falar com o servidor.", "erro");
  } finally {
    recarregando = false;
    if (recarregarDeNovo) {
      recarregarDeNovo = false;
      carregarLista();
    }
  }
}

function linhaDeEnvio(arquivo) {
  const linha = el("div", "upload-row");
  const topo = el("div", "upload-top");
  const nome = el("span", "upload-name", arquivo.name);
  const situacao = el("span", "upload-status", "Na fila");
  topo.append(nome, situacao);
  const trilho = el("div", "upload-track");
  const barra = el("div", "upload-bar");
  barra.style.width = "0%";
  trilho.append(barra);
  linha.append(topo, trilho);
  areaEnvios.append(linha);
  return { linha, barra, situacao };
}

function mensagemDeErro(xhr) {
  if (MENSAGENS_ERRO[xhr.status]) return MENSAGENS_ERRO[xhr.status];
  if (xhr.status === 401) return "Sessão expirada. Entre de novo.";
  if (xhr.status === 403) return "Envio recusado (sessão inválida). Recarregue a página.";
  if (xhr.status === 0) return "Conexão interrompida durante o envio.";
  return `Falha no envio (erro ${xhr.status}).`;
}

async function enviarArquivo(arquivo) {
  const { linha, barra, situacao } = linhaDeEnvio(arquivo);
  const sessao = await api("/api/sessao").then((r) => r.json()).catch(() => null);
  if (!sessao?.csrf) {
    linha.classList.add("upload-erro");
    situacao.textContent = "Sessão expirada. Entre de novo.";
    return;
  }
  await new Promise((resolver) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/cortes/upload");
    xhr.setRequestHeader("X-CSRF-Token", sessao.csrf);
    xhr.upload.onprogress = (evento) => {
      if (!evento.lengthComputable) return;
      const pct = Math.round((evento.loaded / evento.total) * 100);
      barra.style.width = `${pct}%`;
      situacao.textContent = pct >= 100 ? "Gravando…" : `${pct}%`;
    };
    xhr.onload = () => {
      if (xhr.status === 201) {
        barra.style.width = "100%";
        linha.classList.add("upload-ok");
        situacao.textContent = "Enviado";
        setTimeout(() => linha.remove(), 4000);
        showToast(`${arquivo.name} enviado.`, "sucesso");
      } else {
        linha.classList.add("upload-erro");
        situacao.textContent = mensagemDeErro(xhr);
      }
      resolver();
    };
    xhr.onerror = () => {
      linha.classList.add("upload-erro");
      situacao.textContent = mensagemDeErro(xhr);
      resolver();
    };
    situacao.textContent = "0%";
    const dados = new FormData();
    dados.append("arquivo", arquivo);
    xhr.send(dados);
  });
  carregarLista();
}

function enfileirar(arquivos) {
  for (const arquivo of arquivos) {
    fila = fila.then(() => enviarArquivo(arquivo)).catch(() => {});
  }
}

function montarAreaDeEnvio() {
  const zona = el("div", "dropzone");
  zona.tabIndex = 0;
  zona.setAttribute("role", "button");
  zona.append(
    el("p", "dropzone-title", "Arraste os vídeos aqui"),
    el("p", "dropzone-hint", "ou clique para escolher (mp4, mov, mkv, webm, m4v)"),
  );
  const entrada = el("input");
  entrada.type = "file";
  entrada.multiple = true;
  entrada.accept = "video/*";
  entrada.hidden = true;
  zona.append(entrada);

  const escolher = () => entrada.click();
  zona.addEventListener("click", escolher);
  zona.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" || evento.key === " ") {
      evento.preventDefault();
      escolher();
    }
  });
  entrada.addEventListener("click", (evento) => evento.stopPropagation());
  entrada.addEventListener("change", () => {
    enfileirar([...entrada.files]);
    entrada.value = "";
  });
  for (const nome of ["dragenter", "dragover"]) {
    zona.addEventListener(nome, (evento) => {
      evento.preventDefault();
      zona.classList.add("dropzone-ativa");
    });
  }
  for (const nome of ["dragleave", "drop"]) {
    zona.addEventListener(nome, (evento) => {
      evento.preventDefault();
      zona.classList.remove("dropzone-ativa");
    });
  }
  zona.addEventListener("drop", (evento) => enfileirar([...evento.dataTransfer.files]));
  return zona;
}

function renderizar(secao) {
  raiz = secao;
  areaEnvios = el("div", "upload-list");
  areaLista = el("div", "clip-list");
  secao.replaceChildren(montarAreaDeEnvio(), areaEnvios, areaLista);
  carregarLista();
  if (!assinado) {
    assinado = true;
    subscribeEvents(() => {
      if (raiz && !raiz.hidden) carregarLista();
    });
  }
}

document.addEventListener("secao-ativada", (evento) => {
  if (evento.detail?.id === "acervo" && raiz) carregarLista();
});

registerSection("acervo", renderizar, {
  label: "Acervo",
  icon: ICONE_ACERVO,
  subtitle: "Seus cortes, prontos para transcrever.",
});
