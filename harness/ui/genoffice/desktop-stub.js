/*
 * Browser-side stand-in for the Electron preload bridge (`window.desktop`).
 *
 * The real bridge is installed by apps/docs/src/preload/index.ts through
 * contextBridge, so it only exists inside the Electron shell.  The docs
 * renderer itself is plain web code and boots in a browser once the bridge is
 * present, so this file provides the same surface with the minimum behaviour
 * the renderer needs: language/theme preferences, and one document handed over
 * through the one-shot `dataUrl` the renderer fetches with `fetch()`.
 *
 * The document bytes are NOT embedded here.  `dataUrl` points at a path the
 * test driver intercepts, so the corpus file is served over HTTP exactly the
 * way the editor's own handoff URL works.
 */
;(function () {
  var DOC_PATH = '/Users/arthrod/temp/T/editors_trial/fixture/complex.docx'
  var DOC_URL = '/sample.docx'

  // The docs renderer opens the Genspark AI sidebar by default; it eats ~360px
  // of the canvas, which is not what this study measures.  Collapse it so the
  // rendered page gets the full window width.
  try {
    localStorage.setItem('aidocs.showAi', '0')
  } catch (e) {
    /* storage unavailable */
  }

  var listeners = new Map()
  function on(name) {
    return function (handler) {
      var set = listeners.get(name)
      if (!set) {
        set = new Set()
        listeners.set(name, set)
      }
      set.add(handler)
      return function () {
        set.delete(handler)
      }
    }
  }

  var PROVIDER_IDS = [
    'genspark',
    'codex',
    'anthropic',
    'gemini',
    'deepseek',
    'openai',
    'kimi',
    'glm',
    'qwen',
    'doubao',
    'mimo',
    'hunyuan',
    'ling',
    'spark',
    'longcat',
    'minimax',
    'xai',
    'mistral',
    'openrouter',
    'requesty',
  ]

  var impl = {
    // ---- preferences -------------------------------------------------
    getLanguage: async function () {
      return 'en'
    },
    getSystemLocale: async function () {
      return 'en-US'
    },
    getTheme: async function () {
      return 'light'
    },
    getDocumentTheme: async function () {
      return 'follow'
    },
    getAutoSaveDefault: async function () {
      return false
    },
    getAuthorName: async function () {
      return 'Study'
    },
    getAiPanelPrefs: async function () {
      return null
    },
    getRecentFiles: async function () {
      return []
    },
    getAiSettings: async function () {
      var providers = {}
      PROVIDER_IDS.forEach(function (id) {
        providers[id] = { apiKey: '', model: '', baseUrl: '' }
      })
      return { provider: 'anthropic', providers: providers }
    },
    setAiSettings: async function () {
      return { ok: true }
    },
    setAiPanelPrefs: async function () {
      return { ok: true }
    },

    // ---- document open ------------------------------------------------
    // The renderer fetches `dataUrl` exactly once; the driver intercepts it.
    consumePendingOpenDocx: async function () {
      return {
        path: DOC_PATH,
        name: 'complex.docx',
        dataUrl: DOC_URL,
        hash: '0'.repeat(64),
      }
    },
    consumeNewBlankDoc: async function () {
      return false
    },
    consumeAiDocContent: async function () {
      return null
    },
    consumeHeadlessExport: async function () {
      return null
    },
    confirmDocumentReplace: async function () {
      return true
    },
    convertAltChunkHtml: async function () {
      return null
    },
    docPasswordIntentRevision: async function () {
      return 0
    },
    discardDocPasswordIntents: async function () {
      return undefined
    },
    openDocx: async function () {
      return null
    },
    openDocxPath: async function () {
      return null
    },
    openDocxDecrypt: async function () {
      return { ok: false, reason: 'error' }
    },
    createDocument: async function () {
      return { ok: false }
    },

    // ---- fonts / spell / misc -----------------------------------------
    fontMetrics: async function () {
      return null
    },
    spellLanguages: async function () {
      return ['en-US']
    },
    listDocsTabs: async function () {
      return []
    },
    getPathForFile: function () {
      return DOC_PATH
    },
    fetchImage: async function () {
      return null
    },
    pickImage: async function () {
      return null
    },
    pickMergeDataSource: async function () {
      return null
    },
    pickExportImagesTarget: async function () {
      return null
    },
    pickAttachments: async function () {
      return []
    },
    addAttachmentPaths: async function () {
      return { ok: true }
    },
    addPastedImage: async function () {
      return { ok: true }
    },
    readAttachment: async function () {
      return { ok: true, text: '' }
    },
    readAttachmentImage: async function () {
      return null
    },
    copyImageToClipboard: async function () {
      return { ok: true }
    },
    saveImageAs: async function () {
      return { ok: true }
    },
    aiGskStatus: async function () {
      return { loggedIn: false }
    },
    aiGskLogin: async function () {
      return { ok: false }
    },
    skillsList: async function () {
      return []
    },
    skillText: async function () {
      return ''
    },
    webSearch: async function () {
      return []
    },
    imageSearch: async function () {
      return []
    },
    analyzeMedia: async function () {
      return null
    },
    aiGenerateImage: async function () {
      return null
    },
    kbList: async function () {
      return []
    },
    kbSearch: async function () {
      return []
    },
    kbRead: async function () {
      return { ok: true, text: '' }
    },
    runCli: async function () {
      return { ok: true, stdout: '', stderr: '' }
    },
    zoteroCommand: async function () {
      return { ok: true }
    },

    // ---- saving / export (never used by this study) -------------------
    saveDocx: async function () {
      return { ok: true }
    },
    saveDocxAs: async function () {
      return { ok: true }
    },
    saveDocxNew: async function () {
      return { ok: true }
    },
    saveDocxTo: async function () {
      return { ok: true }
    },
    writeRecoveryCopy: async function () {
      return { ok: true }
    },
    exportPdf: async function () {
      return { ok: true }
    },
    exportHtml: async function () {
      return { ok: true }
    },
    exportMarkdown: async function () {
      return { ok: true }
    },
    print: async function () {
      return { ok: true }
    },
    printPdfBuffer: async function () {
      return null
    },
    listPrinters: async function () {
      return []
    },
    saveMergedPdf: async function () {
      return { ok: true }
    },
    takeExportPdf: async function () {
      return null
    },
    writeExportImage: async function () {
      return { ok: true }
    },
    setDocPassword: async function () {
      return { ok: true }
    },
    openNewTab: async function () {
      return { ok: true }
    },
    openSourcePath: async function () {
      return { ok: true }
    },
    focusDocsTab: async function () {
      return undefined
    },

    // ---- fire-and-forget notifications --------------------------------
    armContextMenu: function () {},
    claimContextMenu: function () {},
    spellDiag: function () {},
    headlessExportDone: function () {},
    respondToZotero: function () {},
    reportViewMenuState: function () {},
    reportCloseCheck: function () {},
    reportCloseSaveResult: function () {},
    signalMcpReady: function () {},
    reportMcpResult: function () {},
  }

  var fallback = async function () {
    return undefined
  }

  window.desktop = new Proxy(impl, {
    get: function (target, prop) {
      if (prop in target) return target[prop]
      if (prop === 'then') return undefined
      if (typeof prop === 'string' && prop.slice(0, 2) === 'on') return on(prop)
      return fallback
    },
  })
})()
