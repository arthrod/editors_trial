import {
  history,
  redo,
  undo
} from "./chunk-EEDQKAJD.js";
import {
  Extension,
  callOrReturn,
  getChangedRanges,
  getExtensionField,
  isNodeEmpty,
  isNodeSelection
} from "./chunk-OWH7ZFRL.js";
import "./chunk-CIFUQ556.js";
import "./chunk-U2CEKRTD.js";
import "./chunk-RQAGXNWY.js";
import "./chunk-GUTLX3CO.js";
import "./chunk-WYB3WAZG.js";
import {
  gapCursor
} from "./chunk-JGUEEROG.js";
import "./chunk-Z2SERAUO.js";
import {
  Decoration,
  DecorationSet
} from "./chunk-XKURRMPI.js";
import {
  Plugin,
  PluginKey
} from "./chunk-PFBQI6ML.js";
import {
  dropPoint
} from "./chunk-CP3TIOFU.js";
import "./chunk-YHXBH3KU.js";
import "./chunk-ZLXQMWRS.js";

// ../../node_modules/prosemirror-dropcursor/dist/index.js
function dropCursor(options = {}) {
  return new Plugin({
    view(editorView) {
      return new DropCursorView(editorView, options);
    }
  });
}
var DropCursorView = class {
  constructor(editorView, options) {
    var _a;
    this.editorView = editorView;
    this.cursorPos = null;
    this.element = null;
    this.timeout = -1;
    this.lastDragEvent = null;
    this.width = (_a = options.width) !== null && _a !== void 0 ? _a : 1;
    this.color = options.color === false ? void 0 : options.color || "black";
    this.class = options.class;
    this.handlers = ["dragover", "dragend", "drop", "dragleave"].map((name) => {
      let handler = (e) => {
        this[name](e);
      };
      editorView.dom.addEventListener(name, handler);
      return { name, handler };
    });
  }
  destroy() {
    this.handlers.forEach(({ name, handler }) => this.editorView.dom.removeEventListener(name, handler));
  }
  update(editorView, prevState) {
    if (this.cursorPos != null && prevState.doc != editorView.state.doc) {
      if (this.lastDragEvent) {
        let target = this.computeTarget(this.lastDragEvent);
        if (target == this.cursorPos)
          this.updateOverlay();
        else
          this.setCursor(target);
      } else {
        this.updateOverlay();
      }
    }
  }
  setCursor(pos) {
    if (pos == this.cursorPos)
      return;
    this.cursorPos = pos;
    if (pos == null) {
      this.element.parentNode.removeChild(this.element);
      this.element = null;
    } else {
      this.updateOverlay();
    }
  }
  updateOverlay() {
    let $pos = this.editorView.state.doc.resolve(this.cursorPos);
    let isBlock = !$pos.parent.inlineContent, rect;
    let editorDOM = this.editorView.dom, editorRect = editorDOM.getBoundingClientRect();
    let scaleX = editorRect.width / editorDOM.offsetWidth, scaleY = editorRect.height / editorDOM.offsetHeight;
    if (isBlock) {
      let before = $pos.nodeBefore, after = $pos.nodeAfter;
      if (before || after) {
        let node = this.editorView.nodeDOM(this.cursorPos - (before ? before.nodeSize : 0));
        if (node) {
          let nodeRect = node.getBoundingClientRect();
          let top = before ? nodeRect.bottom : nodeRect.top;
          if (before && after)
            top = (top + this.editorView.nodeDOM(this.cursorPos).getBoundingClientRect().top) / 2;
          let halfWidth = this.width / 2 * scaleY;
          rect = { left: nodeRect.left, right: nodeRect.right, top: top - halfWidth, bottom: top + halfWidth };
        }
      }
    }
    if (!rect) {
      let coords = this.editorView.coordsAtPos(this.cursorPos);
      let halfWidth = this.width / 2 * scaleX;
      rect = { left: coords.left - halfWidth, right: coords.left + halfWidth, top: coords.top, bottom: coords.bottom };
    }
    let parent = this.editorView.dom.offsetParent;
    if (!this.element) {
      this.element = parent.appendChild(document.createElement("div"));
      if (this.class)
        this.element.className = this.class;
      this.element.style.cssText = "position: absolute; z-index: 50; pointer-events: none;";
      if (this.color) {
        this.element.style.backgroundColor = this.color;
      }
    }
    this.element.classList.toggle("prosemirror-dropcursor-block", isBlock);
    this.element.classList.toggle("prosemirror-dropcursor-inline", !isBlock);
    let parentLeft, parentTop;
    if (!parent || parent == document.body && getComputedStyle(parent).position == "static") {
      parentLeft = -pageXOffset;
      parentTop = -pageYOffset;
    } else {
      let rect2 = parent.getBoundingClientRect();
      let parentScaleX = rect2.width / parent.offsetWidth, parentScaleY = rect2.height / parent.offsetHeight;
      parentLeft = rect2.left - parent.scrollLeft * parentScaleX;
      parentTop = rect2.top - parent.scrollTop * parentScaleY;
    }
    this.element.style.left = (rect.left - parentLeft) / scaleX + "px";
    this.element.style.top = (rect.top - parentTop) / scaleY + "px";
    this.element.style.width = (rect.right - rect.left) / scaleX + "px";
    this.element.style.height = (rect.bottom - rect.top) / scaleY + "px";
  }
  scheduleRemoval(timeout) {
    clearTimeout(this.timeout);
    this.timeout = setTimeout(() => this.setCursor(null), timeout);
  }
  computeTarget(event) {
    let pos = this.editorView.posAtCoords({ left: event.clientX, top: event.clientY });
    let node = pos && pos.inside >= 0 && this.editorView.state.doc.nodeAt(pos.inside);
    let disableDropCursor = node && node.type.spec.disableDropCursor;
    let disabled = typeof disableDropCursor == "function" ? disableDropCursor(this.editorView, pos, event) : disableDropCursor;
    if (!pos || disabled)
      return null;
    let target = pos.pos;
    if (this.editorView.dragging && this.editorView.dragging.slice) {
      let point = dropPoint(this.editorView.state.doc, target, this.editorView.dragging.slice);
      if (point != null)
        target = point;
    }
    return target;
  }
  dragover(event) {
    if (!this.editorView.editable)
      return;
    this.lastDragEvent = event;
    let target = this.computeTarget(event);
    if (target != null) {
      this.setCursor(target);
      this.scheduleRemoval(5e3);
    }
  }
  dragend() {
    this.scheduleRemoval(20);
  }
  drop() {
    this.scheduleRemoval(20);
  }
  dragleave(event) {
    if (!this.editorView.dom.contains(event.relatedTarget))
      this.setCursor(null);
  }
};

// ../../node_modules/@tiptap/extensions/dist/index.js
var CharacterCount = Extension.create({
  name: "characterCount",
  addOptions() {
    return {
      limit: null,
      autoTrim: true,
      mode: "textSize",
      textCounter: (text) => text.length,
      wordCounter: (text) => text.split(" ").filter((word) => word !== "").length
    };
  },
  addStorage() {
    return {
      characters: () => 0,
      words: () => 0
    };
  },
  onBeforeCreate() {
    this.storage.characters = (options) => {
      const node = (options === null || options === void 0 ? void 0 : options.node) || this.editor.state.doc;
      if (((options === null || options === void 0 ? void 0 : options.mode) || this.options.mode) === "textSize") {
        const text = node.textBetween(0, node.content.size, void 0, " ");
        return this.options.textCounter(text);
      }
      return node.nodeSize;
    };
    this.storage.words = (options) => {
      const node = (options === null || options === void 0 ? void 0 : options.node) || this.editor.state.doc;
      const text = node.textBetween(0, node.content.size, " ", " ");
      return this.options.wordCounter(text);
    };
  },
  addProseMirrorPlugins() {
    let initialEvaluationDone = false;
    return [new Plugin({
      key: new PluginKey("characterCount"),
      appendTransaction: (transactions, oldState, newState) => {
        if (initialEvaluationDone) return;
        const limit = this.options.limit;
        const autoTrim = this.options.autoTrim;
        if (limit === null || limit === void 0 || limit === 0 || autoTrim === false) {
          initialEvaluationDone = true;
          return;
        }
        const initialContentSize = this.storage.characters({ node: newState.doc });
        if (initialContentSize > limit) {
          const over = initialContentSize - limit;
          const from = 0;
          const to = over;
          console.warn(`[CharacterCount] Initial content exceeded limit of ${limit} characters. Content was automatically trimmed.`);
          const tr = newState.tr.deleteRange(from, to);
          initialEvaluationDone = true;
          return tr;
        }
        initialEvaluationDone = true;
      },
      filterTransaction: (transaction, state) => {
        const limit = this.options.limit;
        if (!transaction.docChanged || limit === 0 || limit === null || limit === void 0) return true;
        const oldSize = this.storage.characters({ node: state.doc });
        const newSize = this.storage.characters({ node: transaction.doc });
        if (newSize <= limit) return true;
        if (oldSize > limit && newSize > limit && newSize <= oldSize) return true;
        if (oldSize > limit && newSize > limit && newSize > oldSize) return false;
        if (!transaction.getMeta("paste")) return false;
        const pos = transaction.selection.$head.pos;
        const from = pos - (newSize - limit);
        const to = pos;
        transaction.deleteRange(from, to);
        if (this.storage.characters({ node: transaction.doc }) > limit) return false;
        return true;
      }
    })];
  }
});
var Dropcursor = Extension.create({
  name: "dropCursor",
  addOptions() {
    return {
      color: "currentColor",
      width: 1,
      class: void 0
    };
  },
  addProseMirrorPlugins() {
    return [dropCursor(this.options)];
  }
});
var Focus = Extension.create({
  name: "focus",
  addOptions() {
    return {
      className: "has-focus",
      mode: "all"
    };
  },
  addProseMirrorPlugins() {
    return [new Plugin({
      key: new PluginKey("focus"),
      props: { decorations: ({ doc, selection }) => {
        const { isEditable, isFocused } = this.editor;
        const { anchor } = selection;
        const decorations = [];
        if (!isEditable || !isFocused) return DecorationSet.create(doc, []);
        let maxLevels = 0;
        if (this.options.mode === "deepest") doc.descendants((node, pos) => {
          if (node.isText) return;
          if (!(anchor >= pos && anchor <= pos + node.nodeSize - 1)) return false;
          maxLevels += 1;
        });
        let currentLevel = 0;
        doc.descendants((node, pos) => {
          if (node.isText) return false;
          if (!(anchor >= pos && anchor <= pos + node.nodeSize - 1)) return false;
          currentLevel += 1;
          if (this.options.mode === "deepest" && maxLevels - currentLevel > 0 || this.options.mode === "shallowest" && currentLevel > 1) return this.options.mode === "deepest";
          decorations.push(Decoration.node(pos, pos + node.nodeSize, { class: this.options.className }));
        });
        return DecorationSet.create(doc, decorations);
      } }
    })];
  }
});
var Gapcursor = Extension.create({
  name: "gapCursor",
  addProseMirrorPlugins() {
    return [gapCursor()];
  },
  extendNodeSchema(extension) {
    var _callOrReturn;
    const context = {
      name: extension.name,
      options: extension.options,
      storage: extension.storage
    };
    return { allowGapCursor: (_callOrReturn = callOrReturn(getExtensionField(extension, "allowGapCursor", context))) !== null && _callOrReturn !== void 0 ? _callOrReturn : null };
  }
});
var DEFAULT_DATA_ATTRIBUTE = "placeholder";
var PLUGIN_KEY = new PluginKey("tiptap__placeholder");
function createPlaceholderDecoration(options) {
  const { editor, placeholder, dataAttribute, pos, node, isEmptyDoc, hasAnchor, classes: { emptyNode, emptyEditor } } = options;
  const classes = [emptyNode];
  if (isEmptyDoc) classes.push(emptyEditor);
  return Decoration.node(pos, pos + node.nodeSize, {
    class: classes.join(" "),
    [dataAttribute]: typeof placeholder === "function" ? placeholder({
      editor,
      node,
      pos,
      hasAnchor
    }) : placeholder
  });
}
function resolveEmptyNodeClass(emptyNodeClass, props) {
  return typeof emptyNodeClass === "function" ? emptyNodeClass(props) : emptyNodeClass;
}
function scanRangeForDecorations({ editor, options, dataAttribute, doc, selection, from, to }) {
  const { anchor } = selection;
  const decorations = [];
  const isEmptyDoc = editor.isEmpty;
  doc.nodesBetween(from, to, (node, pos) => {
    const hasAnchor = anchor >= pos && anchor <= pos + node.nodeSize;
    const isEmpty = !node.isLeaf && isNodeEmpty(node);
    if (!node.type.isTextblock) return options.includeChildren;
    if ((hasAnchor || !options.showOnlyCurrent) && isEmpty) decorations.push(createPlaceholderDecoration({
      editor,
      isEmptyDoc,
      dataAttribute,
      hasAnchor,
      placeholder: options.placeholder,
      classes: {
        emptyEditor: options.emptyEditorClass,
        emptyNode: resolveEmptyNodeClass(options.emptyNodeClass, {
          editor,
          node,
          pos,
          hasAnchor
        })
      },
      node,
      pos
    }));
    return options.includeChildren;
  });
  return decorations;
}
function buildPlaceholderDecorations({ editor, options, dataAttribute, doc, selection }) {
  if (!(editor.isEditable || !options.showOnlyWhenEditable)) return null;
  const { anchor } = selection;
  const decorations = [];
  const isEmptyDoc = editor.isEmpty;
  if (options.showOnlyCurrent && !options.includeChildren) {
    const resolved = doc.resolve(anchor);
    const node = resolved.depth > 0 ? resolved.node(1) : resolved.nodeAfter;
    const nodeStart = resolved.depth > 0 ? resolved.before(1) : anchor;
    if (node && node.type.isTextblock && isNodeEmpty(node)) {
      const hasAnchor = anchor >= nodeStart && anchor <= nodeStart + node.nodeSize;
      decorations.push(createPlaceholderDecoration({
        editor,
        isEmptyDoc,
        dataAttribute,
        hasAnchor,
        placeholder: options.placeholder,
        classes: {
          emptyEditor: options.emptyEditorClass,
          emptyNode: resolveEmptyNodeClass(options.emptyNodeClass, {
            editor,
            node,
            pos: nodeStart,
            hasAnchor
          })
        },
        node,
        pos: nodeStart
      }));
    }
  } else decorations.push(...scanRangeForDecorations({
    editor,
    options,
    dataAttribute,
    doc,
    selection,
    from: 0,
    to: doc.content.size
  }));
  return DecorationSet.create(doc, decorations);
}
function resolveTopLevelRange(doc, pos) {
  const resolved = doc.resolve(pos);
  if (resolved.depth === 0) {
    var _resolved$nodeAfter;
    const node = (_resolved$nodeAfter = resolved.nodeAfter) !== null && _resolved$nodeAfter !== void 0 ? _resolved$nodeAfter : resolved.nodeBefore;
    if (!node) return {
      from: pos,
      to: pos
    };
    const nodePos = resolved.nodeAfter ? pos : pos - node.nodeSize;
    return {
      from: nodePos,
      to: nodePos + node.nodeSize
    };
  }
  const topLevelPos = resolved.before(1);
  return {
    from: topLevelPos,
    to: topLevelPos + resolved.node(1).nodeSize
  };
}
function toContentRelativeRange(doc, range) {
  return {
    from: Math.max(0, range.from - 1),
    to: Math.min(doc.content.size, range.to - 1)
  };
}
function getTopLevelBlocksInRange(doc, from, to) {
  const ranges = [];
  doc.forEach((node, offset) => {
    const nodeStart = offset;
    const nodeEnd = nodeStart + node.nodeSize;
    const absNodeStart = nodeStart + 1;
    const absNodeEnd = nodeEnd + 1;
    if (absNodeStart < to && absNodeEnd > from) ranges.push({
      from: nodeStart,
      to: nodeEnd
    });
  });
  return ranges;
}
function mergeRanges(ranges) {
  if (ranges.length === 0) return [];
  const sorted = [...ranges].sort((a, b) => a.from - b.from);
  const merged = [{ ...sorted[0] }];
  for (let i = 1; i < sorted.length; i += 1) {
    const last = merged[merged.length - 1];
    const current = sorted[i];
    if (current.from <= last.to) last.to = Math.max(last.to, current.to);
    else merged.push({ ...current });
  }
  return merged;
}
function collectBlocksForChange(doc, change) {
  const ranges = getTopLevelBlocksInRange(doc, change.from, change.to);
  ranges.push(toContentRelativeRange(doc, resolveTopLevelRange(doc, change.from)));
  if (change.to > change.from) ranges.push(toContentRelativeRange(doc, resolveTopLevelRange(doc, Math.min(change.to, doc.content.size + 1) - 1)));
  else if (change.from < doc.content.size + 1) ranges.push(toContentRelativeRange(doc, resolveTopLevelRange(doc, Math.min(change.from + 1, doc.content.size))));
  return ranges;
}
function collectRescanRanges(tr, oldState, newState) {
  const ranges = [];
  if (tr.docChanged) {
    const changes = getChangedRanges(tr);
    for (const change of changes) ranges.push(...collectBlocksForChange(newState.doc, change.newRange));
  }
  if (tr.selectionSet) {
    ranges.push(toContentRelativeRange(newState.doc, resolveTopLevelRange(newState.doc, tr.mapping.map(oldState.selection.anchor))));
    ranges.push(toContentRelativeRange(newState.doc, resolveTopLevelRange(newState.doc, newState.selection.anchor)));
  }
  return mergeRanges(ranges);
}
function clampRange(from, to, doc) {
  const clampedFrom = Math.max(0, Math.min(from, doc.content.size));
  return {
    from: clampedFrom,
    to: Math.max(clampedFrom, Math.min(to, doc.content.size))
  };
}
function updateDecorationsInRanges({ decorations, ranges, editor, options, dataAttribute, doc, selection }) {
  let next = decorations;
  for (const range of ranges) {
    const { from, to } = clampRange(range.from, range.to, doc);
    const existing = next.find(from, to).filter((decoration) => decoration.from >= from && decoration.to <= to);
    if (existing.length) next = next.remove(existing);
    const newDecos = scanRangeForDecorations({
      editor,
      options,
      dataAttribute,
      doc,
      selection,
      from,
      to
    });
    if (newDecos.length) next = next.add(doc, newDecos);
  }
  return next;
}
function createPlaceholderStateField({ editor, options, dataAttribute }) {
  return {
    init(_config, state) {
      const decorations = buildPlaceholderDecorations({
        editor,
        options,
        dataAttribute,
        doc: state.doc,
        selection: state.selection
      });
      return decorations !== null && decorations !== void 0 ? decorations : DecorationSet.empty;
    },
    apply(tr, prev, oldState, newState) {
      if (!tr.docChanged && !tr.selectionSet) return prev;
      return updateDecorationsInRanges({
        decorations: prev.map(tr.mapping, tr.doc),
        ranges: collectRescanRanges(tr, oldState, newState),
        editor,
        options,
        dataAttribute,
        doc: newState.doc,
        selection: newState.selection
      });
    }
  };
}
function preparePlaceholderAttribute(attr) {
  return attr.replace(/\s+/g, "-").replace(/[^a-zA-Z0-9-]/g, "").replace(/^[0-9-]+/, "").replace(/^-+/, "").toLowerCase();
}
function createPlaceholderPlugin({ editor, options }) {
  const dataAttribute = options.dataAttribute ? `data-${preparePlaceholderAttribute(options.dataAttribute)}` : `data-${DEFAULT_DATA_ATTRIBUTE}`;
  const useResolvedPath = options.showOnlyCurrent && !options.includeChildren;
  return new Plugin({
    key: PLUGIN_KEY,
    ...useResolvedPath ? {} : { state: createPlaceholderStateField({
      editor,
      options,
      dataAttribute
    }) },
    props: { decorations: useResolvedPath ? ({ doc, selection }) => buildPlaceholderDecorations({
      editor,
      options,
      dataAttribute,
      doc,
      selection
    }) : (state) => {
      var _PLUGIN_KEY$getState;
      if (options.showOnlyWhenEditable && !editor.isEditable) return DecorationSet.empty;
      return (_PLUGIN_KEY$getState = PLUGIN_KEY.getState(state)) !== null && _PLUGIN_KEY$getState !== void 0 ? _PLUGIN_KEY$getState : DecorationSet.empty;
    } }
  });
}
var Placeholder = Extension.create({
  name: "placeholder",
  addOptions() {
    return {
      emptyEditorClass: "is-editor-empty",
      emptyNodeClass: "is-empty",
      dataAttribute: DEFAULT_DATA_ATTRIBUTE,
      placeholder: "Write something …",
      showOnlyWhenEditable: true,
      showOnlyCurrent: true,
      includeChildren: false
    };
  },
  addProseMirrorPlugins() {
    return [createPlaceholderPlugin({
      editor: this.editor,
      options: this.options
    })];
  }
});
function shouldSyncDomSelection(state, editor) {
  return !state.selection.empty && !isNodeSelection(state.selection) && editor.isEditable;
}
function shouldPreserveSelection(state, editor) {
  return shouldSyncDomSelection(state, editor) && !editor.isFocused && !editor.view.dragging;
}
function clearDomSelection() {
  var _window$getSelection;
  (_window$getSelection = window.getSelection()) === null || _window$getSelection === void 0 || _window$getSelection.removeAllRanges();
}
function restoreDomSelection(view) {
  view.focus();
}
var Selection = Extension.create({
  name: "selection",
  addOptions() {
    return { className: "selection" };
  },
  addProseMirrorPlugins() {
    const { editor, options } = this;
    return [new Plugin({
      key: new PluginKey("selection"),
      props: {
        decorations(state) {
          if (!shouldPreserveSelection(state, editor)) return null;
          return DecorationSet.create(state.doc, [Decoration.inline(state.selection.from, state.selection.to, { class: options.className })]);
        },
        handleDOMEvents: {
          blur(view) {
            if (!shouldSyncDomSelection(view.state, editor)) return false;
            clearDomSelection();
            return false;
          },
          focus(view) {
            if (!shouldSyncDomSelection(view.state, editor)) return false;
            requestAnimationFrame(() => {
              if (!editor.isDestroyed && view.hasFocus()) restoreDomSelection(view);
            });
            return false;
          }
        }
      }
    })];
  }
});
var skipTrailingNodeMeta = "skipTrailingNode";
function nodeEqualsType({ types, node }) {
  return node && Array.isArray(types) && types.includes(node.type) || (node === null || node === void 0 ? void 0 : node.type) === types;
}
var TrailingNode = Extension.create({
  name: "trailingNode",
  addOptions() {
    return {
      node: void 0,
      notAfter: []
    };
  },
  addProseMirrorPlugins() {
    var _this$editor$schema$t;
    const plugin = new PluginKey(this.name);
    const defaultNode = this.options.node || ((_this$editor$schema$t = this.editor.schema.topNodeType.contentMatch.defaultType) === null || _this$editor$schema$t === void 0 ? void 0 : _this$editor$schema$t.name) || "paragraph";
    const disabledNodes = Object.entries(this.editor.schema.nodes).map(([, value]) => value).filter((node) => (this.options.notAfter || []).concat(defaultNode).includes(node.name));
    return [new Plugin({
      key: plugin,
      appendTransaction: (transactions, __, state) => {
        const { doc, tr, schema } = state;
        const shouldInsertNodeAtEnd = plugin.getState(state);
        const endPosition = doc.content.size;
        const type = schema.nodes[defaultNode];
        if (transactions.some((transaction) => transaction.getMeta("skipTrailingNode"))) return;
        if (!shouldInsertNodeAtEnd) return;
        return tr.insert(endPosition, type.create());
      },
      state: {
        init: (_, state) => {
          const lastNode = state.tr.doc.lastChild;
          return !nodeEqualsType({
            node: lastNode,
            types: disabledNodes
          });
        },
        apply: (tr, value) => {
          if (!tr.docChanged) return value;
          if (tr.getMeta("__uniqueIDTransaction")) return value;
          const lastNode = tr.doc.lastChild;
          return !nodeEqualsType({
            node: lastNode,
            types: disabledNodes
          });
        }
      }
    })];
  }
});
var UndoRedo = Extension.create({
  name: "undoRedo",
  addOptions() {
    return {
      depth: 100,
      newGroupDelay: 500
    };
  },
  addCommands() {
    return {
      undo: () => ({ state, dispatch }) => {
        return undo(state, dispatch);
      },
      redo: () => ({ state, dispatch }) => {
        return redo(state, dispatch);
      }
    };
  },
  addProseMirrorPlugins() {
    return [history(this.options)];
  },
  addKeyboardShortcuts() {
    return {
      "Mod-z": () => this.editor.commands.undo(),
      "Shift-Mod-z": () => this.editor.commands.redo(),
      "Mod-y": () => this.editor.commands.redo(),
      "Mod-я": () => this.editor.commands.undo(),
      "Shift-Mod-я": () => this.editor.commands.redo()
    };
  }
});
export {
  CharacterCount,
  DEFAULT_DATA_ATTRIBUTE,
  Dropcursor,
  Focus,
  Gapcursor,
  PLUGIN_KEY,
  Placeholder,
  Selection,
  TrailingNode,
  UndoRedo,
  preparePlaceholderAttribute,
  skipTrailingNodeMeta
};
//# sourceMappingURL=@tiptap_extensions.js.map
