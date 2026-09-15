// reporting/assets/report.js
(function () {
  var data = JSON.parse(document.getElementById("report-data").textContent);
  var app = document.getElementById("app");

  // Fix 4 (final whole-branch review): populated as a side effect of
  // every renderTermRef call below, so the structure walk knows exactly
  // which declarations WERE reached via some particle/attribute-use ref.
  // Anything left over after the whole walk (the schema's own single,
  // truly-global root element -- referenced by nobody's content model,
  // since it's the document's own entry point -- and any future
  // schema's equivalent) gets rendered in its own "Global declarations"
  // subsection so it isn't invisible in §1.
  var referencedDeclarationUris = new Set();

  function el(tag, attrs, children) {
    var e = document.createElement(tag);
    attrs = attrs || {};
    for (var k in attrs) {
      if (k === "class") { e.className = attrs[k]; }
      else { e.setAttribute(k, attrs[k]); }
    }
    (children || []).forEach(function (c) { if (c) e.appendChild(c); });
    return e;
  }

  function text(s) { return document.createTextNode(s); }

  function refLink(uri) {
    return el("a", { href: "#" + uri, class: "ref", "data-name": uri }, [text(uri)]);
  }

  // An element/attribute declaration is rendered fully inline wherever a
  // particle or attribute-use references it -- declarations in this
  // corpus are always locally scoped to exactly one containing type, so
  // there is never a second place that would need the same content
  // duplicated. A reference to a named TYPE (extends, an attribute's own
  // type, a union member) instead becomes a real anchor link into that
  // type's own, separately-rendered top-level entry in Structure.
  //
  // The declaration box's own DOM id is deliberately NOT the bare subject
  // URI: the same URI is also used, unprefixed, as the id of that
  // subject's Structure entry (renderComplexType/renderSimpleType) and/or
  // its Documentation-Pairs entry (renderDocPair) -- confirmed against the
  // real whole-corpus report that a large fraction of subjects have both a
  // structural entry and a doc-pair entry, which would otherwise collide.
  // Declarations are never link targets (nothing does refLink(ref) for an
  // element/attribute), so this prefix is safe to add without breaking
  // any existing href="#...".
  function renderTermRef(ref) {
    var decl = data.declarations[ref];
    if (!decl) return refLink(ref);
    referencedDeclarationUris.add(ref);
    var box = el("div", { class: "entry declaration", id: "decl:" + ref, "data-name": decl.name });
    box.appendChild(el("h4", {}, [text(decl.kind + " " + decl.name)]));
    if (decl.type) {
      var typeLine = el("div", { class: "meta" }, [text("type: ")]);
      typeLine.appendChild(refLink(decl.type));
      box.appendChild(typeLine);
    }
    if (decl.default !== null) {
      box.appendChild(el("div", { class: "meta" }, [text("default=" + decl.default)]));
    }
    if (decl.fixed !== null) {
      box.appendChild(el("div", { class: "meta" }, [text("fixed=" + decl.fixed)]));
    }
    if (decl.documentation.de) {
      box.appendChild(el("div", { class: "de" }, [text("DE: " + decl.documentation.de)]));
    }
    if (decl.documentation.en) {
      box.appendChild(el("div", { class: "en" }, [text("EN: " + decl.documentation.en)]));
    }
    return box;
  }

  function renderContentModel(model) {
    var wrap = el("ul", { class: "content-model" });
    wrap.appendChild(el("li", { class: "model-kind" }, [text(model.kind)]));
    model.particles.forEach(function (p) {
      var li = el("li", { class: "particle" });
      li.appendChild(text("[" + p.minOccurs + ".." + p.maxOccurs + "] "));
      if (p.term.nested) {
        li.appendChild(renderContentModel(p.term.nested));
      } else {
        li.appendChild(renderTermRef(p.term.ref));
      }
      wrap.appendChild(li);
    });
    return wrap;
  }

  function renderComplexType(t) {
    var box = el("div", {
      class: "entry complex-type", id: t.uri, "data-name": t.name || t.uri,
    });
    box.appendChild(
      el("h4", {}, [text((t.name || "(anonymous)") + (t.abstract ? " [abstract]" : ""))])
    );
    if (t.extends) {
      var extendsLine = el("div", { class: "meta" }, [text("extends ")]);
      extendsLine.appendChild(refLink(t.extends));
      box.appendChild(extendsLine);
    }
    box.appendChild(renderContentModel(t.contentModel));
    if (t.attributeUses.length) {
      var uses = el("ul", { class: "attribute-uses" });
      t.attributeUses.forEach(function (u) {
        var li = el("li");
        li.appendChild(text(u.required ? "[required] " : "[optional] "));
        li.appendChild(renderTermRef(u.ref));
        uses.appendChild(li);
      });
      box.appendChild(uses);
    }
    if (t.identityConstraints.length) {
      var ics = el("ul", { class: "identity-constraints" });
      t.identityConstraints.forEach(function (ic) {
        var line = ic.kind + " selector=" + ic.selector + " fields=[" +
          ic.fields.join(", ") + "]" + (ic.refer ? " refer=" + ic.refer : "");
        ics.appendChild(el("li", {}, [text(line)]));
      });
      box.appendChild(ics);
    }
    return box;
  }

  function renderSimpleType(t) {
    var box = el("div", {
      class: "entry simple-type", id: t.uri, "data-name": t.name || t.uri,
    });
    box.appendChild(el("h4", {}, [text(t.name || "(anonymous)")]));
    var facetKeys = Object.keys(t.facets);
    if (facetKeys.length) {
      var facetsText = facetKeys.map(function (k) { return k + "=" + t.facets[k]; }).join(", ");
      box.appendChild(el("div", { class: "meta" }, [text("facets: " + facetsText)]));
    }
    if (t.enumeration.length) {
      box.appendChild(el("div", { class: "meta" }, [text("enumeration: " + t.enumeration.join(", "))]));
    }
    if (t.patterns.length) {
      box.appendChild(el("div", { class: "meta" }, [text("pattern: " + t.patterns.join(", "))]));
    }
    if (t.unionMembers.length) {
      var um = el("div", { class: "meta" }, [text("union of: ")]);
      t.unionMembers.forEach(function (m, i) {
        if (i > 0) um.appendChild(text(", "));
        um.appendChild(refLink(m));
      });
      box.appendChild(um);
    }
    return box;
  }

  function renderStructure() {
    var root = el("div", { class: "section", id: "section-structure" });
    var nsBoxes = {};
    Object.keys(data.structure).sort().forEach(function (ns) {
      var nsBlock = data.structure[ns];
      var nsBox = el("div", { class: "namespace" });
      nsBox.appendChild(el("h3", {}, [text(ns)]));
      nsBlock.complexTypes.forEach(function (t) { nsBox.appendChild(renderComplexType(t)); });
      nsBlock.simpleTypes.forEach(function (t) { nsBox.appendChild(renderSimpleType(t)); });
      nsBoxes[ns] = nsBox;
      root.appendChild(nsBox);
    });

    // Fix 4: anything in data.declarations never reached by the walk
    // above (via renderTermRef) gets its own "Global declarations"
    // subsection, grouped by the same uri.split("#", 1)[0] namespace
    // convention reporting/data.py's own build_structure uses. Wrapped
    // in a .doc-group (not just a bare heading) so the search filter's
    // empty-container-hiding logic (Fix 3) applies to it too.
    var unreferencedByNamespace = {};
    Object.keys(data.declarations).forEach(function (uri) {
      if (referencedDeclarationUris.has(uri)) return;
      var ns = uri.split("#")[0];
      (unreferencedByNamespace[ns] = unreferencedByNamespace[ns] || []).push(uri);
    });
    Object.keys(unreferencedByNamespace).sort().forEach(function (ns) {
      var nsBox = nsBoxes[ns];
      if (!nsBox) {
        nsBox = el("div", { class: "namespace" });
        nsBox.appendChild(el("h3", {}, [text(ns)]));
        nsBoxes[ns] = nsBox;
        root.appendChild(nsBox);
      }
      var groupBox = el("div", { class: "doc-group global-declarations" });
      groupBox.appendChild(el("h4", {}, [text("Global declarations")]));
      unreferencedByNamespace[ns].sort().forEach(function (uri) {
        groupBox.appendChild(renderTermRef(uri));
      });
      nsBox.appendChild(groupBox);
    });

    return root;
  }

  // Prefixed for the same reason as renderTermRef's declaration id above:
  // a doc-pair's subject URI is also, unprefixed, the id of that same
  // subject's Structure/declaration entry elsewhere on the page. Doc-pair
  // entries are never link targets, so the prefix is safe to add.
  function renderDocPair(pair, kind) {
    var box = el("div", {
      class: "entry doc-pair " + kind, id: "doc:" + pair.uri, "data-name": pair.name,
    });
    box.appendChild(el("h4", {}, [text(pair.name)]));
    // Fix 1: an "englishOnly" pair has no "de" field at all (that's the
    // whole point -- no German documentation exists for it), so the DE
    // line only renders when there is one.
    if (pair.de !== undefined) {
      box.appendChild(el("div", { class: "de" }, [text("DE: " + pair.de)]));
    }
    if (kind === "matched") {
      box.appendChild(el("div", { class: "en" }, [text("EN: " + pair.en)]));
      pair.issues.forEach(function (issue) {
        box.appendChild(el("div", { class: "issue" }, [text(issue.kind + ": " + issue.detail)]));
      });
    } else if (kind === "ambiguous") {
      var cand = el("ul", { class: "candidates" });
      pair.candidates.forEach(function (c) { cand.appendChild(el("li", {}, [text(c)])); });
      box.appendChild(cand);
    } else if (kind === "englishOnly") {
      box.appendChild(el("div", { class: "en" }, [text("EN: " + pair.en)]));
    }
    return box;
  }

  function renderDocs() {
    var root = el("div", { class: "section", id: "section-docs" });
    // Fix 1 (final whole-branch review): "English-only" is a 4th real
    // group (reporting/data.py's build_documentation_pairs) for subjects
    // with real @en documentation but no German at all -- previously
    // silently dropped entirely; now rendered like the other 3 groups so
    // §2's total subject count reconciles with §3's coverage total.
    [["matched", "Matched"], ["unmatched", "Unmatched"], ["ambiguous", "Ambiguous"],
     ["englishOnly", "English-only"]]
      .forEach(function (pair) {
        var key = pair[0], label = pair[1];
        var groupBox = el("div", { class: "doc-group" });
        groupBox.appendChild(
          el("h3", {}, [text(label + " (" + data.documentationPairs[key].length + ")")])
        );
        data.documentationPairs[key].forEach(function (p) {
          groupBox.appendChild(renderDocPair(p, key));
        });
        root.appendChild(groupBox);
      });
    return root;
  }

  function renderAudit() {
    var root = el("div", { class: "section", id: "section-audit" });
    var numbers = el("div", { class: "audit-numbers" });
    ["attachment", "coverage"].forEach(function (key) {
      var block = data.audit[key];
      var line = Object.keys(block).map(function (k) { return k + "=" + block[k]; }).join(", ");
      numbers.appendChild(el("div", {}, [text(key + ": " + line)]));
    });
    root.appendChild(numbers);
    var issues = el("ul", { class: "audit-issues" });
    data.audit.issues.forEach(function (issue) {
      var li = el("li", { "data-name": issue.subjectName });
      li.appendChild(text("[" + issue.kind + "] " + issue.subjectName + " -- " + issue.detail));
      issues.appendChild(li);
    });
    root.appendChild(issues);
    return root;
  }

  var sections = {
    structure: renderStructure(),
    docs: renderDocs(),
    audit: renderAudit(),
  };
  Object.keys(sections).forEach(function (key) {
    app.appendChild(sections[key]);
    sections[key].style.display = key === "structure" ? "" : "none";
  });

  document.querySelectorAll("#nav button[data-section]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      Object.keys(sections).forEach(function (key) {
        sections[key].style.display = key === btn.dataset.section ? "" : "none";
      });
      document.querySelectorAll("#nav button[data-section]").forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
    });
  });

  // Fix 3 (final whole-branch review): the previous logic hid a
  // non-matching .entry outright, including complex/simple-type entries
  // that CONTAIN a matching declaration .entry (renderTermRef nests
  // declarations inside their containing type's own .entry) -- via
  // normal DOM/CSS containment, hiding the parent also hides the
  // matching child, even though the child itself was never told to hide.
  // Verified live: searching "Paymentlines" (a real element name; most
  // real Structure entries are nested declarations, not top-level types)
  // returned zero visible results. The Audit section's issue <li>
  // elements also had no hookup into search at all.
  //
  // Fix: collect every candidate (.entry, plus Audit's own issue <li>s),
  // find which ones match the term directly, then walk UP the DOM from
  // each match and mark every ancestor .entry/.namespace/.doc-group as
  // visible too -- so a matching nested declaration keeps its parent
  // type (and that type's own namespace) visible. Anything not matched
  // and not an ancestor of a match stays hidden, which also naturally
  // hides a namespace/doc-group left with zero visible entries.
  function searchCandidates() {
    return document.querySelectorAll(".entry, .audit-issues li");
  }

  function containerAncestors() {
    return document.querySelectorAll(".namespace, .doc-group");
  }

  function applySearchFilter(term) {
    term = term.toLowerCase();
    var candidates = searchCandidates();
    var containers = containerAncestors();

    if (!term) {
      candidates.forEach(function (c) { c.style.display = ""; });
      containers.forEach(function (c) { c.style.display = ""; });
      return;
    }

    candidates.forEach(function (c) { c.style.display = "none"; });
    containers.forEach(function (c) { c.style.display = "none"; });

    candidates.forEach(function (c) {
      var name = (c.dataset.name || "").toLowerCase();
      if (name.indexOf(term) === -1) return;
      c.style.display = "";
      var node = c.parentElement;
      while (node && node !== app) {
        if (
          node.classList &&
          (node.classList.contains("entry") ||
            node.classList.contains("namespace") ||
            node.classList.contains("doc-group"))
        ) {
          node.style.display = "";
        }
        node = node.parentElement;
      }
    });
  }

  document.getElementById("search").addEventListener("input", function (e) {
    applySearchFilter(e.target.value);
  });
})();
