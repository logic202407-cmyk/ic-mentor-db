/* 算法评测页（/eval）的渲染层。
 *
 * 硬约束（有测试钉住）：
 *   1. 源码里不出现任何指标数字常量。上面显示的每个数都来自 /api/evaluation/summary，
 *      接口只读 workbench/reference/eval/retrieval.json 与 workbench/evaluation/*.json。
 *      这里只做格式化与几何换算，不做重算、不补零、不给默认值顶上。
 *   2. 产物缺失（directions / disambiguation 为 null）时渲染「待产出」与复现入口，
 *      绝不显示 0 或占位假数字。
 *   3. 只用手写 SVG 与 CSS 条形，不引任何外部库，离线可用。
 *
 * 图表统一遵守同一套无障碍策略：图本身给出 aria-label 摘要，每行可聚焦并带完整数值的
 * aria-label，另附「数值表」折叠块作为文字替代。
 */
(function () {
  "use strict";

  var API = "/api/evaluation/summary";
  var NS = "http://www.w3.org/2000/svg";

  /* 主对比图的三档指标。键名与产物字段一一对应，改键名就等于改口径，所以集中在这里。 */
  var MAIN_METRICS = [
    { key: "ndcg@10", label: "NDCG@10", cls: "s1" },
    { key: "recall@20", label: "Recall@20", cls: "s2" },
    { key: "mrr@10", label: "MRR@10", cls: "s3" }
  ];

  var FILTER_LABELS = {
    unfiltered_test: "不过滤",
    absolute_test: "绝对阈值",
    margin_test: "间隔阈值",
    combined_test: "组合过滤"
  };

  var PROTOCOL_LABELS = {
    primary: "主口径（同校同名）",
    reviewed: "复核后口径",
    supplementary: "补充口径（跨校同名）",
    combined: "全部同名组合"
  };

  /* ────────────────────────── 基础工具 ────────────────────────── */

  function $(id) { return document.getElementById(id); }

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined && text !== null) node.textContent = String(text);
    return node;
  }

  function clear(node) { while (node && node.firstChild) node.removeChild(node.firstChild); }

  function isNum(v) { return typeof v === "number" && isFinite(v); }

  function has(v) { return v !== undefined && v !== null && v !== ""; }

  /** 0–1 的比例 → 百分比文本。只有真数字才格式化，其余一律破折号。 */
  function pct(v) {
    if (!isNum(v)) return "—";
    return (v * 100).toFixed(1) + "%";
  }

  /** 带正负号的百分点差（输入仍是 0–1 比例）。 */
  function pctDelta(v) {
    if (!isNum(v)) return "—";
    var s = Math.abs(v * 100).toFixed(1) + " 个百分点";
    if (v > 0) return "+" + s;
    if (v < 0) return "−" + s;
    return "±" + s;
  }

  function num(v, digits) {
    if (!isNum(v)) return "—";
    return v.toFixed(has(digits) ? digits : 1);
  }

  function int(v) {
    if (!isNum(v)) return "—";
    return String(Math.round(v));
  }

  function plain(v) {
    if (!has(v)) return "—";
    if (typeof v === "number") return isNum(v) ? String(v) : "—";
    return String(v);
  }

  /** 2026-10-23T15:32:09+0800 → 2026-10-23 15:32（时区另标，避免读者以为是本地时区）。 */
  function formatTime(raw) {
    if (!has(raw)) return "—";
    var s = String(raw);
    var head = s.slice(0, 16).replace("T", " ");
    var zone = s.length > 19 ? s.slice(19) : "";
    return zone ? head + "（" + zone + "）" : head;
  }

  function safe(fn) {
    try { fn(); } catch (err) {
      if (window.console && console.warn) console.warn("[eval] 渲染失败", err);
    }
  }

  /* ────────────────────────── 通用块 ────────────────────────── */

  function kv(pairs) {
    var dl = el("dl", "kv");
    pairs.forEach(function (pair) {
      if (!pair) return;
      dl.appendChild(el("dt", null, pair[0]));
      dl.appendChild(el("dd", null, pair[1]));
    });
    return dl;
  }

  function codeBlock(text) {
    var pre = el("pre", "code-block", text);
    return pre;
  }

  function table(captionText, headers, rows) {
    var wrap = el("div", "table-wrap");
    var t = el("table", "data-table");
    if (captionText) t.appendChild(el("caption", null, captionText));
    var thead = el("thead");
    var tr = el("tr");
    headers.forEach(function (h) {
      var th = el("th", null, h.label || h);
      th.setAttribute("scope", "col");
      if (h && h.num) th.className = "num";
      tr.appendChild(th);
    });
    thead.appendChild(tr);
    t.appendChild(thead);
    var tbody = el("tbody");
    rows.forEach(function (cells) {
      var row = el("tr");
      cells.forEach(function (cell, i) {
        var td = el("td", i > 0 ? "num" : null);
        if (cell instanceof Node) td.appendChild(cell);
        else td.textContent = plain(cell);
        row.appendChild(td);
      });
      tbody.appendChild(row);
    });
    t.appendChild(tbody);
    wrap.appendChild(t);
    return wrap;
  }

  /* ────────────────────────── 条形图 ────────────────────────── */

  /**
   * 一行条形：标签 + N 个「轨道 + 填充 + 数值」。
   * 整行可聚焦，aria-label 里带上完整数值——键盘和读屏都能拿到图上看得见的信息。
   */
  function barLine(opts) {
    var row = el("div");
    row.className = "bar-line" + (opts.two ? " two" : "") + (opts.best ? " is-best" : "");
    if (opts.focusable !== false) row.setAttribute("tabindex", "0");

    var label = el("span", "bar-label");
    label.appendChild(document.createTextNode(opts.label));
    if (opts.badge) label.appendChild(el("i", null, opts.badge));
    row.appendChild(label);

    var spoken = [opts.label];
    opts.cells.forEach(function (cell) {
      var wrap = el("span", "bar-cell");
      var track = el("span", "bar-track");
      var fill = el("span", "bar-fill " + (cell.cls || "s1"));
      if (isNum(cell.value)) {
        var w = Math.max(0, Math.min(100, cell.value * 100));
        fill.style.width = w + "%";
        if (w > 0) fill.style.minWidth = "2px";
      } else {
        fill.style.width = "0%";
      }
      track.appendChild(fill);
      wrap.appendChild(track);
      var val = el("b", "bar-val" + (isNum(cell.value) && cell.value === 0 ? " is-zero" : ""), cell.text);
      wrap.appendChild(val);
      row.appendChild(wrap);
      spoken.push((cell.series || "") + " " + cell.text);
    });

    var spokenText = spoken.join("，");
    row.setAttribute("aria-label", spokenText);
    row.setAttribute("title", spokenText);
    return row;
  }

  function barHead(labels, two) {
    var head = el("div", "bar-line bar-head" + (two ? " two" : ""));
    labels.forEach(function (l) { head.appendChild(el("span", null, l)); });
    return head;
  }

  function legend(items) {
    var box = el("div", "legend");
    items.forEach(function (it) {
      var span = el("span");
      var swatch = el("i");
      swatch.style.background = it.color;
      span.appendChild(swatch);
      span.appendChild(document.createTextNode(it.label));
      box.appendChild(span);
    });
    return box;
  }

  function barColor(cls) {
    var map = { s1: "#215b52", s2: "#7a5a1e", s3: "#41637f", ghost: "#b6c6c1", muted: "#657074" };
    return map[cls] || map.s1;
  }

  /* ────────────────────────── SVG 工具 ────────────────────────── */

  function svgEl(name, attrs) {
    var node = document.createElementNS(NS, name);
    if (attrs) {
      Object.keys(attrs).forEach(function (k) { node.setAttribute(k, attrs[k]); });
    }
    return node;
  }

  function svgText(x, y, text, cls, anchor) {
    var t = svgEl("text", { x: x, y: y, class: cls || "tick" });
    if (anchor) t.setAttribute("text-anchor", anchor);
    t.textContent = text;
    return t;
  }

  /* ────────────────────────── 摘要 ────────────────────────── */

  function statCard(label, value, note, isText) {
    var card = el("div", "stat-card");
    card.appendChild(el("p", "stat-label", label));
    card.appendChild(el("p", "stat-value" + (isText ? " is-text" : ""), value));
    if (note) card.appendChild(el("p", "stat-note", note));
    return card;
  }

  function renderSummary(data) {
    var host = $("summaryCards");
    if (!host) return;
    clear(host);

    var corpus = data.corpus || {};
    var config = data.config || {};
    var queries = config.queries || {};
    var devTest = queries.dev !== undefined && queries.test !== undefined
      ? int(queries.dev) + " / " + int(queries.test) : "—";
    var totalQueries = isNum(queries.A) && isNum(queries.B) ? int(queries.A + queries.B) : "—";

    host.appendChild(statCard(
      "评测生成时间",
      formatTime(data.generated_at),
      "本机实跑后写入产物文件",
      true
    ));

    host.appendChild(statCard(
      "语料规模",
      isNum(corpus.entries) ? int(corpus.entries) + " 条" : "—",
      isNum(corpus.engineering_entries) ? "其中工科 " + int(corpus.engineering_entries) + " 条" : ""
    ));

    host.appendChild(statCard(
      "查询数",
      totalQueries + " 条",
      isNum(queries.A) && isNum(queries.B)
        ? "A 类 " + int(queries.A) + " / B 类 " + int(queries.B) : ""
    ));

    host.appendChild(statCard(
      "dev / test 划分",
      devTest,
      "seed " + plain(config.seed) + " · dev_ratio " + plain(config.dev_ratio)
    ));

    host.appendChild(statCard(
      "单次返回上限",
      isNum(config.return_limit) ? int(config.return_limit) + " 条" : "—",
      "所有指标都在这个截断下计算"
    ));

    var res = data.retrieval && data.retrieval.resources ? data.retrieval.resources : {};
    host.appendChild(statCard(
      "本次评测耗时",
      isNum(res.wall_seconds) ? num(res.wall_seconds) + " 秒" : "—",
      res.cpu && isNum(res.cpu.cpu_utilization)
        ? "CPU 利用率 " + num(res.cpu.cpu_utilization) + "%（多核累计）" : ""
    ));

    var lede = $("summaryLede");
    if (lede) {
      lede.textContent = "语料 " + (isNum(corpus.entries) ? int(corpus.entries) : "—")
        + " 条、查询 " + totalQueries + " 条，按 dev/test 分开；"
        + "阈值、权重只在 dev 上选，下面所有指标都报在 test 上。";
    }

    var honesty = $("honestyText");
    if (honesty) {
      honesty.textContent = has(data.honesty) ? data.honesty
        : "产物里没有写诚实口径字段；此时请把本页数字当作工程自检，而不是准确率。";
    }

    var extra = $("honestyExtra");
    if (extra) {
      var terms = (config && config.terminology_map) || null;
      extra.textContent = "读法：这些数字衡量的是「在本仓库自己的弱监督标签上，哪条检索路径排得更靠前」，"
        + "它可以用来比较方法之间的相对高低，但不能换算成「用户找到导师的概率」。"
        + (terms && terms.entries ? "B 类查询的术语映射表共 " + int(terms.entries) + " 条。" : "");
    }

    var cmd = $("reproduceCommand");
    if (cmd) cmd.textContent = has(data.how_to_reproduce) ? data.how_to_reproduce : "python -m workbench.retrieval_eval";

    var note = $("reproduceNote");
    if (note) {
      note.textContent = "产物按 config 里的固定种子划分 dev/test；同一台机器上重跑，划分与指标应当逐位复现。";
    }

    var list = $("sourceList");
    if (list) {
      clear(list);
      var sources = data.sources || {};
      var entries = [
        ["检索指标、失败案例、延迟、权重扫描", sources.retrieval],
        ["方向推断留出验证", sources.directions],
        ["同名消歧评测", sources.disambiguation],
        ["同名消歧显著性检验", sources.significance]
      ];
      entries.forEach(function (pair) {
        if (!has(pair[1])) return;
        var li = el("li");
        li.appendChild(document.createTextNode(pair[0] + "："));
        li.appendChild(el("code", null, pair[1]));
        list.appendChild(li);
      });
    }
  }

  /* ────────────────────────── 方法对比 ────────────────────────── */

  function splitOf(method, split) {
    if (!method) return {};
    if (split === "a") return method.a_test || {};
    if (split === "b") return method.b_test || {};
    if (split === "dev") return method.all_dev || {};
    return method.all_test || {};
  }

  function renderMethodChart(hostId, tableId, noteId, methods, split, splitLabel) {
    var host = $(hostId);
    if (!host) return;
    clear(host);

    host.appendChild(barHead(["方法", "NDCG@10", "Recall@20", "MRR@10"], false));

    // 最优行按 NDCG@10 判定，只做视觉强调，数值本身照原样打印。
    var bestKey = null;
    var bestVal = -1;
    methods.forEach(function (m) {
      var v = splitOf(m, split)["ndcg@10"];
      if (isNum(v) && v > bestVal) { bestVal = v; bestKey = m.key; }
    });

    methods.forEach(function (m) {
      var row = splitOf(m, split);
      var cells = MAIN_METRICS.map(function (metric) {
        var v = row[metric.key];
        return {
          value: v,
          text: pct(v),
          cls: metric.cls,
          series: metric.label
        };
      });
      host.appendChild(barLine({
        label: m.label || m.key,
        cells: cells,
        best: m.key === bestKey
      }));
    });

    var note = $(noteId);
    if (note) {
      var q = methods.length ? splitOf(methods[0], split).queries : null;
      note.textContent = splitLabel + " 共 " + (isNum(q) ? int(q) : "—")
        + " 条查询；条形长度就是指标值（0–100% 满刻度，两个分区同一把尺子，可以直接对看）。"
        + "加粗的是本区 NDCG@10 最高的一行。";
    }

    if (tableId) {
      var tableHost = $(tableId);
      if (tableHost) {
        clear(tableHost);
        var keys = [];
        methods.forEach(function (m) {
          Object.keys(splitOf(m, split)).forEach(function (k) {
            if (keys.indexOf(k) < 0) keys.push(k);
          });
        });
        var headers = ["方法"].concat(keys);
        var rows = methods.map(function (m) {
          var row = splitOf(m, split);
          return [m.label || m.key].concat(keys.map(function (k) {
            var v = row[k];
            if (!isNum(v)) return "—";
            // 查询数与相关文档数是计数，其余按比例显示。
            if (k === "queries" || k === "median_relevant") return int(v);
            return pct(v);
          }));
        });
        tableHost.appendChild(table("", headers, rows));
      }
    }
  }

  function findMethod(methods, key) {
    for (var i = 0; i < methods.length; i++) {
      if (methods[i].key === key) return methods[i];
    }
    return null;
  }

  function bestOf(methods, split) {
    var best = null, bestVal = -1;
    methods.forEach(function (m) {
      var v = splitOf(m, split)["ndcg@10"];
      if (isNum(v) && v > bestVal) { bestVal = v; best = m; }
    });
    return best ? { method: best, value: bestVal } : null;
  }

  function renderCallout(data, methods) {
    var host = $("calloutAbBody");
    if (!host) return;
    clear(host);

    var kw = findMethod(methods, "keyword_substring") || methods[0];
    var bm25 = findMethod(methods, "bm25");
    var hybrid = findMethod(methods, "hybrid_score");
    var rrf = findMethod(methods, "hybrid_rrf");

    var lead = el("p");
    lead.textContent = "A 类查询本身就是学科名、方向名、兴趣词的原文，词面匹配能直接命中；"
      + "B 类查询是口语化的描述，用户不会照着方向标签的措辞提问，字面重合度极低。"
      + "向量分支提供的是语义上的近邻，正好补上这部分缺口，所以混合的收益主要在 B 类显现；"
      + "在 A 类，词面方法已经接近上限，向量分支只能带来摊薄与噪声。"
      + "下面这几行是这句话的检验结果——如果数字和它不一致，以数字为准。";
    host.appendChild(lead);

    var bestA = bestOf(methods, "a");
    var bestB = bestOf(methods, "b");
    var rows = [];
    rows.push(["A 类最好", bestA ? (bestA.method.label || bestA.method.key) + " · NDCG@10 " + pct(bestA.value) : "—"]);
    rows.push(["B 类最好", bestB ? (bestB.method.label || bestB.method.key) + " · NDCG@10 " + pct(bestB.value) : "—"]);

    [
      ["混合（加权）", hybrid],
      ["混合（RRF）", rrf]
    ].forEach(function (pair) {
      if (!pair[1]) return;
      var a = splitOf(pair[1], "a")["ndcg@10"];
      var b = splitOf(pair[1], "b")["ndcg@10"];
      var vsKwA = isNum(a) && isNum(splitOf(kw, "a")["ndcg@10"]) ? a - splitOf(kw, "a")["ndcg@10"] : null;
      var vsKwB = isNum(b) && isNum(splitOf(kw, "b")["ndcg@10"]) ? b - splitOf(kw, "b")["ndcg@10"] : null;
      rows.push([
        pair[0] + "相对关键词基线",
        "A 类 " + pctDelta(vsKwA) + "；B 类 " + pctDelta(vsKwB)
      ]);
    });

    if (bm25) {
      var bA = splitOf(bm25, "a")["ndcg@10"];
      var bB = splitOf(bm25, "b")["ndcg@10"];
      if (hybrid) {
        var hA = splitOf(hybrid, "a")["ndcg@10"];
        var hB = splitOf(hybrid, "b")["ndcg@10"];
        rows.push([
          "混合（加权）相对 BM25",
          "A 类 " + pctDelta(isNum(hA) && isNum(bA) ? hA - bA : null)
            + "；B 类 " + pctDelta(isNum(hB) && isNum(bB) ? hB - bB : null)
        ]);
      }
    }

    host.appendChild(kv(rows));

    var caveat = el("p", "micro", "注意 B 类的绝对值整体很低：这不是图表没画好，"
      + "而是这组口语查询本来就难。任何方法在 B 类上的占比都很小，看得是相对高低。");
    caveat.style.marginTop = "10px";
    caveat.style.marginBottom = "0";
    host.appendChild(caveat);
  }

  /* ────────────────────────── 过滤前后 ────────────────────────── */

  function renderFilter(filter) {
    var host = $("chartFilter");
    if (!host) return;
    clear(host);

    var before = filter.unfiltered_test || {};
    var after = filter.combined_test || {};

    host.appendChild(barHead(["指标", FILTER_LABELS.unfiltered_test, FILTER_LABELS.combined_test], true));

    var items = [
      ["ndcg@10", "NDCG@10"],
      ["top1", "Top-1 命中"],
      ["recall@10", "Recall@10"]
    ];
    items.forEach(function (pair) {
      host.appendChild(barLine({
        label: pair[1],
        two: true,
        cells: [
          { value: before[pair[0]], text: pct(before[pair[0]]), cls: "ghost", series: "不过滤" },
          { value: after[pair[0]], text: pct(after[pair[0]]), cls: "s1", series: "组合过滤" }
        ]
      }));
    });

    var note = $("noteFilter");
    if (note) {
      var diffs = items.map(function (p) {
        var a = before[p[0]], b = after[p[0]];
        return isNum(a) && isNum(b) ? Math.abs(a - b) : 0;
      });
      var maxDiff = Math.max.apply(null, diffs);
      var trim = after.trim_ratio;
      var emptyRate = after.empty_rate;

      if (isNum(trim) && trim === 0 && maxDiff === 0) {
        note.textContent = "在 test 上，不过滤与组合过滤的指标完全一致：trim_ratio 为 "
          + pct(trim) + "、empty_rate 为 " + pct(emptyRate)
          + "，也就是没有一条结果落进被裁掉的区间。所以过滤在这里既没有提分也没有掉分——"
          + "它当前的作用是给低置信度结果兜底，而不是提高排序质量。";
      } else if (maxDiff === 0) {
        note.textContent = "在 test 上两组指标的差异为零，但产物记录了被裁掉的比例：trim_ratio "
          + pct(trim) + "、empty_rate " + pct(emptyRate) + "。裁剪没有改变指标，需要结合样本量读。";
      } else {
        note.textContent = "组合过滤相对不过滤的 NDCG@10 变化：" + pctDelta((after["ndcg@10"] || 0) - (before["ndcg@10"] || 0))
          + "（trim_ratio " + pct(trim) + "、empty_rate " + pct(emptyRate) + "）。";
      }
    }

    var tableHost = $("filterTable");
    if (tableHost) {
      clear(tableHost);
      var metrics = ["ndcg@10", "top1", "recall@10", "avg_returned", "trim_ratio", "empty_rate"];
      var rows = Object.keys(FILTER_LABELS).map(function (key) {
        var row = filter[key] || {};
        return [FILTER_LABELS[key]].concat(metrics.map(function (m) {
          if (!isNum(row[m])) return "—";
          if (m === "avg_returned") return num(row[m]);
          return pct(row[m]);
        }));
      });
      tableHost.appendChild(table(
        "四档过滤在 test 上的同一组指标。",
        ["过滤档位"].concat(metrics),
        rows
      ));
    }
  }

  /* ────────────────────────── 权重扫描折线 ────────────────────────── */

  function renderSweep(rows, chosenConfig) {
    var host = $("chartSweep");
    if (!host) return;
    clear(host);

    chosenConfig = chosenConfig && typeof chosenConfig === "object" ? chosenConfig : {};
    var chosen = chosenConfig.hybrid_bm25_weight;
    var bOnlyWeight = chosenConfig.hybrid_bm25_weight_on_dev_B_only;

    var pts = (rows || []).filter(function (r) { return r && isNum(r.bm25_weight); });
    var legendHost = $("legendSweep");
    if (legendHost) clear(legendHost);

    if (!pts.length) {
      host.appendChild(el("p", "quiet", "产物里没有权重扫描记录。"));
      return;
    }

    var series = [
      { key: "ndcg@10", label: "全部查询", cls: "all" },
      { key: "ndcg@10_A", label: "A 类", cls: "a" },
      { key: "ndcg@10_B", label: "B 类", cls: "b" }
    ].filter(function (s) {
      return pts.some(function (p) { return isNum(p[s.key]); });
    });

    var W = 760, H = 280, padL = 52, padR = 18, padT = 16, padB = 34;
    var plotW = W - padL - padR;
    var plotH = H - padT - padB;

    var xMin = Math.min.apply(null, pts.map(function (p) { return p.bm25_weight; }));
    var xMax = Math.max.apply(null, pts.map(function (p) { return p.bm25_weight; }));

    var ys = [];
    series.forEach(function (s) {
      pts.forEach(function (p) { if (isNum(p[s.key])) ys.push(p[s.key]); });
    });
    var yMin = Math.min.apply(null, ys);
    var yMax = Math.max.apply(null, ys);
    var span = yMax - yMin;
    if (!(span > 0)) span = Math.max(Math.abs(yMax), 1);
    var y0 = Math.max(0, yMin - span / 8);
    var y1 = Math.min(1, yMax + span / 8);
    if (!(y1 - y0 > 0)) { y0 = 0; y1 = 1; }

    function px(v) {
      if (!(xMax - xMin > 0)) return padL + plotW / 2;
      return padL + ((v - xMin) / (xMax - xMin)) * plotW;
    }
    function py(v) {
      return padT + (1 - (v - y0) / (y1 - y0)) * plotH;
    }

    var svg = svgEl("svg", {
      class: "svg-chart",
      viewBox: "0 0 " + W + " " + H,
      role: "img",
      "aria-labelledby": "sweepTitle sweepDesc"
    });
    var title = svgEl("title", { id: "sweepTitle" });
    title.textContent = "BM25 权重与 NDCG@10 的关系";
    svg.appendChild(title);
    var desc = svgEl("desc", { id: "sweepDesc" });
    desc.textContent = "横轴是混合打分里 BM25 的权重，纵轴是 NDCG@10。"
      + series.map(function (s) { return "包含 " + s.label + " 一条曲线"; }).join("；")
      + "。逐点数值见下方数值表。";
    svg.appendChild(desc);

    // 横向网格 + 纵轴刻度
    var gridCount = 4;
    for (var g = 0; g <= gridCount; g++) {
      var gv = y0 + (y1 - y0) * g / gridCount;
      var gy = py(gv);
      svg.appendChild(svgEl("line", { x1: padL, y1: gy, x2: padL + plotW, y2: gy, class: "grid" }));
      svg.appendChild(svgText(padL - 8, gy + 4, pct(gv), "tick", "end"));
    }

    // 坐标轴
    svg.appendChild(svgEl("line", { x1: padL, y1: padT + plotH, x2: padL + plotW, y2: padT + plotH, class: "axis" }));
    svg.appendChild(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: padT + plotH, class: "axis" }));

    // 横轴刻度
    var xTicks = 4;
    for (var t = 0; t <= xTicks; t++) {
      var xv = xMin + (xMax - xMin) * t / xTicks;
      svg.appendChild(svgText(px(xv), padT + plotH + 16, num(xv, 2), "tick", "middle"));
    }
    svg.appendChild(svgText(padL + plotW / 2, H - 4, "BM25 权重（混合打分中词面分支的占比）", "axis-label", "middle"));

    // 最终选定的权重：竖虚线，标出「调参停在哪」
    if (isNum(chosen) && chosen >= xMin && chosen <= xMax) {
      var cx = px(chosen);
      svg.appendChild(svgEl("line", { x1: cx, y1: padT, x2: cx, y2: padT + plotH, class: "pick" }));
      svg.appendChild(svgText(cx + 6, padT + 12, "选定 " + num(chosen, 2), "pick-label", "start"));
    }

    // 曲线
    series.forEach(function (s) {
      var seq = pts.filter(function (p) { return isNum(p[s.key]); });
      if (!seq.length) return;
      var d = seq.map(function (p) { return px(p.bm25_weight).toFixed(1) + "," + py(p[s.key]).toFixed(1); }).join(" ");
      svg.appendChild(svgEl("polyline", { points: d, class: "series " + s.cls }));

      seq.forEach(function (p) {
        var c = svgEl("circle", { cx: px(p.bm25_weight), cy: py(p[s.key]), r: 3, class: "dot " + s.cls });
        var ct = svgEl("title");
        ct.textContent = s.label + " · BM25 权重 " + num(p.bm25_weight, 2) + " → NDCG@10 " + pct(p[s.key]);
        c.appendChild(ct);
        svg.appendChild(c);
      });
    });

    host.appendChild(svg);

    if (legendHost) {
      series.forEach(function (s) {
        var span = el("span");
        var swatch = el("i");
        swatch.style.background = barColor(s.cls === "all" ? "s1" : s.cls === "a" ? "s3" : "s2");
        span.appendChild(swatch);
        var last = null;
        pts.forEach(function (p) { if (isNum(p[s.key])) last = p[s.key]; });
        span.appendChild(document.createTextNode(s.label + "（末点 " + pct(last) + "）"));
        legendHost.appendChild(span);
      });
    }

    var note = $("noteSweep");
    if (note) {
      var atChosen = nearestPoint(pts, chosen);
      // 这里只读曲线上的现有数值做对照，不重算选参。
      if (atChosen && isNum(atChosen["ndcg@10_B"])) {
        note.textContent = "曲线取自调参阶段的 dev 划分（与 ALL/dev 的指标逐点吻合），红色竖线是最终选定的权重 "
          + num(chosen, 2) + "。在该权重下 B 类 NDCG@10 为 " + pct(atChosen["ndcg@10_B"])
          + "，而全部查询（A 类占多数）为 " + pct(atChosen["ndcg@10"])
          + "——统一一套权重时，A 类的话语权更大。";
      } else {
        note.textContent = "曲线取自调参阶段在 dev 划分上的扫描，红色竖线是最终选定的权重 " + num(chosen, 2) + "。";
      }
      var bOnlyWeightValue = bOnlyWeight;
      if (isNum(bOnlyWeightValue)) {
        var atB = nearestPoint(pts, bOnlyWeightValue);
        if (atB && isNum(atB["ndcg@10_B"])) {
          note.textContent += " 另：如果只在 B 类上选权重，选出的是 " + num(bOnlyWeight, 2)
            + "，那时 B 类 NDCG@10 是 " + pct(atB["ndcg@10_B"])
            + "——统一一套权重与分工调参的差距就在这两个数之间。";
        }
      }
    }

    var tableHost = $("sweepTable");
    if (tableHost) {
      clear(tableHost);
      var cols = ["bm25_weight"].concat(series.map(function (s) { return s.key; }));
      var rowsOut = pts.map(function (p) {
        return cols.map(function (c) {
          return isNum(p[c]) ? (c === "bm25_weight" ? num(p[c], 2) : pct(p[c])) : "—";
        });
      });
      tableHost.appendChild(table(
        "逐点数值：每一行是一个 BM25 权重。",
        ["BM25 权重"].concat(series.map(function (s) { return s.label + " NDCG@10"; })),
        rowsOut
      ));
    }
  }

  function nearestPoint(pts, x) {
    if (!isNum(x) || !pts.length) return null;
    var best = null, bestD = Infinity;
    pts.forEach(function (p) {
      var d = Math.abs(p.bm25_weight - x);
      if (d < bestD) { bestD = d; best = p; }
    });
    return best;
  }

  /* ────────────────────────── 延迟 ────────────────────────── */

  function renderLatency(latency) {
    var host = $("chartLatency");
    if (!host) return;
    clear(host);

    var keys = (latency && typeof latency === "object") ? Object.keys(latency) : [];
    if (!keys.length) {
      host.appendChild(el("p", "quiet", "产物里没有延迟记录。"));
      return;
    }

    var maxVal = 0;
    keys.forEach(function (k) {
      var row = latency[k] || {};
      ["mean_ms", "median_ms", "p95_ms"].forEach(function (m) {
        if (isNum(row[m]) && row[m] > maxVal) maxVal = row[m];
      });
    });
    if (!(maxVal > 0)) maxVal = 1;

    host.appendChild(barHead(["方法", "均值", "中位数", "P95"], false));

    var labelMap = methodLabelMap();
    keys.forEach(function (k) {
      var row = latency[k] || {};
      var cells = [
        { key: "mean_ms", cls: "s1", label: "均值" },
        { key: "median_ms", cls: "s2", label: "中位数" },
        { key: "p95_ms", cls: "s3", label: "P95" }
      ].map(function (m) {
        var v = row[m.key];
        return {
          value: isNum(v) ? v / maxVal : null,
          text: isNum(v) ? num(v) + " ms" : "—",
          cls: m.cls,
          series: m.label
        };
      });
      host.appendChild(barLine({ label: labelMap[k] || k, cells: cells }));
    });

    var note = $("noteLatency");
    if (note) {
      var n = latency[keys[0]] && latency[keys[0]].n;
      note.textContent = "条形按本次最大值缩放（最大 " + num(maxVal) + " ms），所以快的那条会接近不可见——"
        + "跨数量级的差距本身就是结论之一。"
        + (isNum(n) ? "每种方法各计时 " + int(n) + " 次。" : "")
        + "混合方法没有单独的计时记录：它复用两路的打分，产物里没有为它单开一项。";
    }

    var tableHost = $("latencyTable");
    if (tableHost) {
      clear(tableHost);
      var labelMap2 = methodLabelMap();
      var rows = keys.map(function (k) {
        var row = latency[k] || {};
        return [
          labelMap2[k] || k,
          isNum(row.n) ? int(row.n) : "—",
          isNum(row.mean_ms) ? num(row.mean_ms) : "—",
          isNum(row.median_ms) ? num(row.median_ms) : "—",
          isNum(row.p95_ms) ? num(row.p95_ms) : "—",
          isNum(row.max_ms) ? num(row.max_ms) : "—"
        ];
      });
      tableHost.appendChild(table(
        "单次查询延迟（毫秒）。",
        ["方法", "样本数", "均值", "中位数", "P95", "最大"],
        rows
      ));
    }
  }

  var LABEL_CACHE = {};

  function methodLabelMap() { return LABEL_CACHE; }

  function renderResources(res) {
    var host = $("resourcesBlock");
    if (!host) return;
    clear(host);
    if (!res || typeof res !== "object") return;

    host.appendChild(el("h4", null, "本次运行的资源占用"));
    var pairs = [];
    if (isNum(res.wall_seconds)) pairs.push(["墙钟耗时", num(res.wall_seconds) + " 秒"]);
    if (res.cpu) {
      if (isNum(res.cpu.user_seconds)) pairs.push(["CPU 用户态", num(res.cpu.user_seconds) + " 秒"]);
      if (isNum(res.cpu.total_seconds)) pairs.push(["CPU 合计", num(res.cpu.total_seconds) + " 秒"]);
      if (isNum(res.cpu.cpu_utilization)) pairs.push(["CPU 利用率", num(res.cpu.cpu_utilization) + "%（多核累计）"]);
    }
    if (pairs.length) host.appendChild(kv(pairs));

    var phases = res.phase_wall_seconds;
    if (phases && typeof phases === "object") {
      var keys = Object.keys(phases);
      var maxV = 0;
      keys.forEach(function (k) { if (isNum(phases[k]) && phases[k] > maxV) maxV = phases[k]; });
      if (maxV > 0) {
        host.appendChild(el("p", "chart-note", "按阶段拆开的墙钟耗时（条形按本区最大值缩放）："));
        var bars = el("div", "bars");
        keys.forEach(function (k) {
          var v = phases[k];
          bars.appendChild(barLine({
            label: k,
            focusable: true,
            cells: [{
              value: isNum(v) ? v / maxV : null,
              text: isNum(v) ? num(v) + " 秒" : "—",
              cls: "s1",
              series: "耗时"
            }]
          }));
        });
        // 阶段图只有一列，改成两列的栅格更紧凑。
        bars.style.setProperty("--bar-cols", "minmax(120px,196px) minmax(0,1fr)");
        host.appendChild(bars);
      }
    }
  }

  /* ────────────────────────── 方向推断 ────────────────────────── */

  function pendingBlock(opts) {
    var box = el("div", "notice notice--pending");
    box.appendChild(el("h3", null, "待产出"));
    var p = el("p");
    p.textContent = opts.summary;
    box.appendChild(p);

    if (opts.path) {
      var pathLine = el("p");
      pathLine.appendChild(document.createTextNode("接口期望的产物路径："));
      pathLine.appendChild(el("code", "inline", opts.path));
      box.appendChild(pathLine);
    }

    if (opts.command) {
      box.appendChild(el("p", "micro", opts.commandNote || "现有的复现入口（在当前实现里写到别的位置，需要把产物放进上面那个路径）："));
      box.appendChild(codeBlock(opts.command));
    }

    if (opts.extra) {
      var extra = el("ul", "pending-list");
      opts.extra.forEach(function (line) {
        extra.appendChild(el("li", null, line));
      });
      box.appendChild(extra);
    }
    return box;
  }

  function renderDirections(directions, sources) {
    var host = $("directionsBody");
    if (!host) return;
    clear(host);

    if (!directions || typeof directions !== "object") {
      host.appendChild(pendingBlock({
        summary: "方向推断的留出验证还没有入库。这里不显示 0，也不显示占位数字——没有产物就不给数字。",
        path: sources && sources.directions,
        command: "python -m workbench.infer_directions --validate N",
        commandNote: "现有验证入口（N 为抽样条数；当前写到 .workbench-data/direction-inference/validation.json）：",
        extra: [
          "该分区会显示：抽样条数、方向词表大小、关键词基线与嵌入模型的 Top-1/Top-3，以及原文照抄（verbatim）与非照抄（non_verbatim）两种分层的差异。",
          "产物放进上面的路径后，刷新本页即可看到真实数字，页面代码不需要改。"
        ]
      }));
      return;
    }

    host.appendChild(kv([
      ["抽样条数", has(directions.sampled) ? int(directions.sampled) : "—"],
      ["方向词表", has(directions.vocab_size) ? int(directions.vocab_size) + " 个标签" : "—"],
      ["耗时", isNum(directions.seconds) ? num(directions.seconds) + " 秒" : "—"]
    ]));

    var methods = [
      ["keyword", "关键词基线"],
      ["embedding", "嵌入模型"],
      ["hybrid", "混合（关键词优先）"]
    ];

    var maxTop3 = 0;
    methods.forEach(function (m) {
      var row = directions[m[0]];
      if (row && isNum(row.top3) && row.top3 > maxTop3) maxTop3 = row.top3;
    });
    if (!(maxTop3 > 0)) maxTop3 = 1;

    host.appendChild(el("p", "chart-note", "同一批记录、藏起方向标签后只靠文本预测："));
    var bars = el("div", "bars");
    bars.style.setProperty("--bar-cols", "minmax(150px,200px) repeat(2,minmax(0,1fr))");
    bars.appendChild(barHead(["方法", "Top-1", "Top-3"], true));
    methods.forEach(function (m) {
      var row = directions[m[0]] || {};
      bars.appendChild(barLine({
        label: m[1],
        two: true,
        cells: [
          { value: row.top1, text: pct(row.top1), cls: "s1", series: "Top-1" },
          { value: isNum(row.top3) ? row.top3 / maxTop3 : null, text: pct(row.top3), cls: "s3", series: "Top-3" }
        ]
      }));
    });
    host.appendChild(bars);
    host.appendChild(el("p", "chart-note",
      "Top-1 与 Top-3 用同一把 0–100% 的尺子；Top-3 条形按本区最大值缩放，具体数值以标签为准。"));

    var strata = directions.strata || {};
    var verb = strata.verbatim || strata["verbatim"];
    var nonVerb = strata.non_verbatim || strata["non_verbatim"];
    if (verb && nonVerb) {
      host.appendChild(el("h4", null, "分层：方向标签是否照抄原文"));
      host.appendChild(kv([
        ["原文照抄", has(verb.n) ? int(verb.n) + " 条；嵌入 Top-1 " + pct(verb.embedding_top1)
          + "；关键词 Top-1 " + pct(verb.keyword_top1) : "—"],
        ["非照抄", has(nonVerb.n) ? int(nonVerb.n) + " 条；嵌入 Top-1 " + pct(nonVerb.embedding_top1)
          + "；关键词 Top-1 " + pct(nonVerb.keyword_top1) : "—"]
      ]));
      host.appendChild(el("p", "micro",
        "分层的意义：原文照抄的那部分靠字面就能命中，非照抄的那部分才是模型真正在「理解」。"
        + "两层的差距越大，说明关键词基线的高分越依赖抄回来的措辞。"));
    }

    host.appendChild(rawFields(directions, "方向推断产物的原始字段"));
  }

  /* ────────────────────────── 同名消歧 ────────────────────────── */

  function renderDisambiguation(disamb, sources) {
    var host = $("disambiguationBody");
    if (!host) return;
    clear(host);

    if (!disamb || typeof disamb !== "object") {
      host.appendChild(pendingBlock({
        summary: "同名消歧的评测产物还没有入库。这一节不显示 0、不显示 AUC 占位值，也不拿旧数字顶上。",
        path: sources && sources.disambiguation,
        command: "python -m workbench.disambiguate_names --evaluate --gold",
        commandNote: "现有评测入口（当前写到 .workbench-data/name-disambiguation/，独立复核集写到 workbench/evaluation/gold_pairs.json）：",
        extra: [
          "该分区会显示：主口径与复核后口径的标签对数、正负例、被排除的「待核」对数、AUC，以及按阈值切的 precision / recall / F1 曲线。",
          "阈值曲线是这一节的重点：它说明「宁可漏判也不要错并」这种取舍在哪个点上成立。"
        ]
      }));
      return;
    }

    var order = ["primary", "reviewed", "supplementary", "combined"];
    var present = order.filter(function (k) {
      return disamb[k] && typeof disamb[k] === "object";
    });

    if (!present.length) {
      host.appendChild(el("p", "quiet", "产物存在但里面没有可比对的口径字段。"));
      host.appendChild(rawFields(disamb, "同名消歧产物的原始字段"));
      return;
    }

    present.forEach(function (key) {
      var block = disamb[key] || {};
      var box = el("div", "callout");
      box.appendChild(el("h3", null, PROTOCOL_LABELS[key] || key));
      if (has(block.scope)) {
        box.appendChild(el("p", "micro", String(block.scope)));
      }
      box.appendChild(kv([
        ["标注对数", has(block.labelled_pairs) ? int(block.labelled_pairs) : "—"],
        ["正例（同人）", has(block.positives) ? int(block.positives) : "—"],
        ["负例（异人）", has(block.negatives) ? int(block.negatives) : "—"],
        ["排除的待核", has(block.excluded_unknown) ? int(block.excluded_unknown) : "—"]
      ]));

      if (block.auc && typeof block.auc === "object") {
        var aucPairs = Object.keys(block.auc).map(function (k) {
          var v = block.auc[k];
          return [k, isNum(v) ? (v <= 1 ? num(v, 3) : num(v)) : plain(v)];
        });
        if (aucPairs.length) {
          box.appendChild(el("h4", null, "AUC"));
          box.appendChild(kv(aucPairs));
        }
      }

      if (block.baseline_institution && typeof block.baseline_institution === "object") {
        var basePairs = Object.keys(block.baseline_institution).map(function (k) {
          var v = block.baseline_institution[k];
          return [k, isNum(v) ? (v <= 1 ? num(v, 3) : num(v)) : plain(v)];
        });
        if (basePairs.length) {
          box.appendChild(el("h4", null, "基线：仅按机构名判定"));
          box.appendChild(kv(basePairs));
        }
      }

      host.appendChild(box);

      if (Array.isArray(block.thresholds) && block.thresholds.length) {
        renderThresholdCurve(host, block.thresholds, (PROTOCOL_LABELS[key] || key));
      }
    });

    host.appendChild(rawFields(disamb, "同名消歧产物的原始字段"));
  }

  /**
   * 阈值曲线：产物里每个阈值点的键名可能随实现变化，这里按「名字里含 precision / recall /
   * f1 / threshold」去探测，找不到就退化成表格——绝不假设某一种键名而画出空图。
   */
  function renderThresholdCurve(host, rows, label) {
    var probe = rows[0] || {};
    var keys = Object.keys(probe);

    function findKey(fragment) {
      var lower = fragment.toLowerCase();
      for (var i = 0; i < keys.length; i++) {
        if (String(keys[i]).toLowerCase().indexOf(lower) >= 0 && isNum(probe[keys[i]])) return keys[i];
      }
      return null;
    }

    var xKey = findKey("threshold") || findKey("tau");
    var pKey = findKey("precision");
    var rKey = findKey("recall");
    var fKey = findKey("f1");

    if (!xKey || (!pKey && !rKey && !fKey)) {
      host.appendChild(table(
        label + "：阈值逐点数值",
        keys,
        rows.map(function (r) {
          return keys.map(function (k) {
            var v = r[k];
            if (isNum(v)) return Math.abs(v) <= 1 ? num(v, 3) : num(v);
            return plain(v);
          });
        })
      ));
      return;
    }

    var series = [];
    if (pKey) series.push({ key: pKey, label: "precision", cls: "all" });
    if (rKey) series.push({ key: rKey, label: "recall", cls: "a" });
    if (fKey) series.push({ key: fKey, label: "F1", cls: "b" });

    var W = 760, H = 260, padL = 52, padR = 18, padT = 16, padB = 34;
    var plotW = W - padL - padR, plotH = H - padT - padB;

    var xs = rows.map(function (r) { return r[xKey]; }).filter(isNum);
    var xMin = Math.min.apply(null, xs), xMax = Math.max.apply(null, xs);

    function px(v) {
      if (!(xMax - xMin > 0)) return padL + plotW / 2;
      return padL + ((v - xMin) / (xMax - xMin)) * plotW;
    }
    function py(v) { return padT + (1 - v) * plotH; }

    var svg = svgEl("svg", {
      class: "svg-chart",
      viewBox: "0 0 " + W + " " + H,
      role: "img",
      "aria-labelledby": "thTitle thDesc"
    });
    var title = svgEl("title", { id: "thTitle" });
    title.textContent = label + "：阈值与 precision / recall / F1";
    svg.appendChild(title);
    var desc = svgEl("desc", { id: "thDesc" });
    desc.textContent = "横轴是判定阈值，纵轴是 0 到 1 的指标值。逐点数值见下方原始字段表。";
    svg.appendChild(desc);

    for (var g = 0; g <= 4; g++) {
      var gv = g / 4;
      var gy = py(gv);
      svg.appendChild(svgEl("line", { x1: padL, y1: gy, x2: padL + plotW, y2: gy, class: "grid" }));
      svg.appendChild(svgText(padL - 8, gy + 4, num(gv, 2), "tick", "end"));
    }
    svg.appendChild(svgEl("line", { x1: padL, y1: padT + plotH, x2: padL + plotW, y2: padT + plotH, class: "axis" }));
    svg.appendChild(svgEl("line", { x1: padL, y1: padT, x2: padL, y2: padT + plotH, class: "axis" }));

    for (var t = 0; t <= 4; t++) {
      var xv = xMin + (xMax - xMin) * t / 4;
      svg.appendChild(svgText(px(xv), padT + plotH + 16, num(xv, 2), "tick", "middle"));
    }
    svg.appendChild(svgText(padL + plotW / 2, H - 4, "判定阈值", "axis-label", "middle"));

    series.forEach(function (s) {
      var pts = rows.filter(function (r) { return isNum(r[xKey]) && isNum(r[s.key]); });
      if (!pts.length) return;
      var d = pts.map(function (r) { return px(r[xKey]).toFixed(1) + "," + py(r[s.key]).toFixed(1); }).join(" ");
      svg.appendChild(svgEl("polyline", { points: d, class: "series " + s.cls }));
      pts.forEach(function (r) {
        var c = svgEl("circle", { cx: px(r[xKey]), cy: py(r[s.key]), r: 3, class: "dot " + s.cls });
        var ct = svgEl("title");
        ct.textContent = s.label + " @ " + num(r[xKey], 2) + " → " + num(r[s.key], 3);
        c.appendChild(ct);
        svg.appendChild(c);
      });
    });

    var wrap = el("div", "svg-wrap");
    wrap.appendChild(svg);
    host.appendChild(wrap);

    var lg = $("legendSweep");
    if (lg) {
      lg.appendChild(legend([
        { color: barColor("s1"), label: "precision" },
        { color: barColor("s3"), label: "recall" },
        { color: barColor("s2"), label: "F1" }
      ]));
    }

    host.appendChild(table(
      label + "：阈值逐点数值",
      [xKey].concat(series.map(function (s) { return s.key; })),
      rows.map(function (r) {
        return [num(r[xKey], 2)].concat(series.map(function (s) {
          return isNum(r[s.key]) ? num(r[s.key], 3) : "—";
        }));
      })
    ));
  }

  /* ────────────────────────── 显著性检验 ────────────────────────── */

  var RATIO_WORDS = ["precision", "recall", "f1", "auc", "share", "ratio", "rate", "top1", "top3"];

  function looksRatio(name) {
    var k = String(name).toLowerCase();
    if (k === "p") return true;
    return RATIO_WORDS.some(function (w) { return k.indexOf(w) >= 0; });
  }

  function formatField(name, value) {
    if (Array.isArray(value)) {
      return "[" + value.map(function (v) {
        return isNum(v) ? (looksRatio(name) || Math.abs(v) <= 1 ? pct(v) : num(v)) : plain(v);
      }).join(", ") + "]";
    }
    if (isNum(value)) {
      if (looksRatio(name)) return pct(value);
      // 计数量（k / n / tp / fp / fn）是整数，带小数会被误读成比例。
      if (value % 1 === 0) return String(value);
      return Math.abs(value) <= 1 ? num(value, 3) : num(value);
    }
    return plain(value);
  }

  function renderSignificance(sig) {
    var host = $("significanceBody");
    if (!host) return;
    clear(host);

    if (!sig || typeof sig !== "object" || !Object.keys(sig).length) {
      return;
    }

    host.appendChild(el("h3", null, "已入库的显著性检验"));
    host.appendChild(el("p", "chart-note",
      "下面这组数字来自同名消歧的显著性检验产物，和上面的主评测是两个文件。"
      + "它给出的是「比例 + Wilson 区间」的形式：只看点估计会把小样本的波动读成效果。"));

    var rows = [];
    Object.keys(sig).forEach(function (name) {
      var entry = sig[name];
      if (!entry || typeof entry !== "object") {
        rows.push([el("code", null, name), plain(entry), "—"]);
        return;
      }
      var parts = Object.keys(entry).filter(function (k) {
        return !Array.isArray(entry[k]);
      }).map(function (k) {
        return k + " " + formatField(k, entry[k]);
      });
      var bands = Object.keys(entry).filter(function (k) {
        return Array.isArray(entry[k]);
      }).map(function (k) {
        return k + " " + formatField(k, entry[k]);
      });
      rows.push([el("code", null, name), parts.join(" · ") || "—", bands.join(" · ") || "—"]);
    });

    var wrap = el("div", "table-wrap");
    var t = el("table", "data-table");
    t.appendChild(el("caption", null, "显著性检验逐项数值（来自 significance.json，未做任何改写）"));
    var thead = el("thead");
    var tr = el("tr");
    ["条目", "点估计与样本量", "置信区间（Wilson）"].forEach(function (h) {
      var th = el("th", null, h);
      th.setAttribute("scope", "col");
      tr.appendChild(th);
    });
    thead.appendChild(tr);
    t.appendChild(thead);
    var tbody = el("tbody");
    rows.forEach(function (cells) {
      var row = el("tr");
      cells.forEach(function (cell) {
        var td = el("td");
        if (cell instanceof Node) td.appendChild(cell);
        else td.textContent = cell;
        row.appendChild(td);
      });
      tbody.appendChild(row);
    });
    t.appendChild(tbody);
    wrap.appendChild(t);
    host.appendChild(wrap);
  }

  /* ────────────────────────── 原始字段（兜底展示） ────────────────────────── */

  function flatten(obj, prefix, out, depth) {
    depth = depth || 0;
    Object.keys(obj).forEach(function (k) {
      var v = obj[k];
      var key = prefix ? prefix + "." + k : k;
      if (v && typeof v === "object" && !Array.isArray(v) && depth < 3) {
        flatten(v, key, out, depth + 1);
      } else if (Array.isArray(v)) {
        var note = "数组（" + v.length + " 项）";
        if (v.length && typeof v[0] !== "object") {
          note = v.slice(0, 6).map(String).join("、") + (v.length > 6 ? " …" : "");
        }
        out.push([key, note]);
      } else {
        out.push([key, formatField(k, v)]);
      }
    });
    return out;
  }

  function rawFields(obj, caption) {
    var details = el("details", "data-fold");
    details.appendChild(el("summary", null, caption + "（逐字段，未改写）"));
    var pairs = flatten(obj, "", [], 0);
    var wrap = el("table", "data-table");
    var tbody = el("tbody");
    pairs.forEach(function (pair) {
      var tr = el("tr");
      var th = el("th", null, pair[0]);
      th.setAttribute("scope", "row");
      tr.appendChild(th);
      var td = el("td", null, pair[1]);
      tr.appendChild(td);
      tbody.appendChild(tr);
    });
    wrap.appendChild(tbody);
    var box = el("div", "table-wrap");
    box.appendChild(wrap);
    details.appendChild(box);
    return details;
  }

  /* ────────────────────────── 失败案例 ────────────────────────── */

  function renderFailures(failures) {
    var body = $("failuresBody");
    if (!body) return;
    clear(body);

    var meta = $("failuresMeta");
    var list = Array.isArray(failures) ? failures : [];

    if (!list.length) {
      var tr = el("tr");
      var td = el("td", null, "产物里没有失败分析记录。这不代表没有失败，只是还没有人逐条分析。");
      td.colSpan = 5;
      tr.appendChild(td);
      body.appendChild(tr);
      if (meta) meta.textContent = "";
      return;
    }

    if (meta) {
      var kinds = {};
      list.forEach(function (f) {
        var k = has(f.kind) ? String(f.kind) : "未分类";
        kinds[k] = (kinds[k] || 0) + 1;
      });
      var kindText = Object.keys(kinds).map(function (k) { return k + " " + kinds[k] + " 条"; }).join("、");
      meta.textContent = "共 " + list.length + " 条，按类型：" + kindText + "。";
    }

    list.forEach(function (f) {
      var row = el("tr");

      var qCell = el("td", "cell-query");
      qCell.textContent = has(f.query) ? String(f.query) : (has(f.ref) ? String(f.ref) : "—");
      if (has(f.kind)) {
        var kind = el("div", "cell-quiet");
        kind.textContent = String(f.kind) + (has(f.expect) ? " · 期望 " + String(f.expect) : "");
        qCell.appendChild(kind);
      }
      row.appendChild(qCell);

      var mCell = el("td");
      mCell.textContent = LABEL_CACHE[f.method] || plain(f.method);
      row.appendChild(mCell);

      var cCell = el("td");
      cCell.textContent = plain(f.category);
      row.appendChild(cCell);

      var topCell = el("td", "cell-top");
      var tops = Array.isArray(f.top) ? f.top : [];
      if (tops.length) {
        var first = tops[0] || {};
        var b = el("b", null, has(first.name) ? String(first.name) : "—");
        topCell.appendChild(b);
        if (has(first.direction)) {
          var d = el("div", "cell-quiet");
          d.textContent = String(first.direction);
          topCell.appendChild(d);
        }
        if (isNum(first.score)) {
          var s = el("div", "cell-quiet");
          s.textContent = "得分 " + num(first.score, 3);
          topCell.appendChild(s);
        }
        if (tops.length > 1) {
          var rest = el("div", "cell-quiet");
          rest.textContent = "次选：" + tops.slice(1).map(function (t) {
            return (has(t.name) ? String(t.name) : "—");
          }).join("、");
          topCell.appendChild(rest);
        }
      } else {
        topCell.textContent = "—";
      }
      row.appendChild(topCell);

      var eCell = el("td");
      eCell.textContent = has(f.extra) ? String(f.extra) : "—";
      row.appendChild(eCell);

      body.appendChild(row);
    });
  }

  /* ────────────────────────── 边界与局限 ────────────────────────── */

  function renderAcronyms(acronyms) {
    var host = $("acronymBlock");
    if (!host) return;
    clear(host);
    if (!acronyms || !acronyms.probes) {
      host.appendChild(el("p", "quiet", "产物里没有缩写审计记录。"));
      return;
    }

    var groups = Array.isArray(acronyms.groups) ? acronyms.groups.slice() : [];
    groups.sort(function (a, b) { return (b.size || 0) - (a.size || 0); });
    var biggest = groups[0] || null;

    var p = el("p");
    p.textContent = "把 " + int(acronyms.probes) + " 个常见英文缩写逐个送进嵌入模型，"
      + int(acronyms.probes) + " 个探针只得到了 " + int(acronyms.distinct_vectors) + " 个不同的向量。";
    host.appendChild(p);

    if (biggest && biggest.size > 1) {
      var members = Array.isArray(biggest.members) ? biggest.members : [];
      var p2 = el("p");
      p2.textContent = "其中最大的一组有 " + int(biggest.size) + " 个成员（"
        + members.slice(0, 8).join("、") + (members.length > 8 ? " 等" : "")
        + "），它们的向量指纹完全相同（指纹 " + plain(biggest.fingerprint) + "），"
        + "也就是编码后是同一个向量，余弦相似度为 1。";
      host.appendChild(p2);

      var p3 = el("p");
      p3.textContent = "后果很直接：在向量检索里，「" + (members[0] || "?") + "」和「"
        + (members[1] || members[0] || "?") + "」是同一个查询，排序完全一样。"
        + "所以这些缩写必须走关键词或术语表，不能只信语义检索。";
      host.appendChild(p3);
    }

    var rows = Array.isArray(acronyms.rows) ? acronyms.rows : [];
    if (rows.length) {
      var unk = rows.filter(function (r) {
        return has(r.tokens) && String(r.tokens).indexOf("[UNK]") >= 0;
      }).length;
      if (unk) {
        var p4 = el("p", "micro");
        p4.textContent = "根因在分词：这 " + int(unk) + " 个缩写在分词阶段就变成了 [UNK]，"
          + "模型拿到的输入几乎只剩 [CLS] 与 [SEP]，向量自然分不开。";
        host.appendChild(p4);
      }
      var details = el("details", "data-fold");
      details.appendChild(el("summary", null, "逐个缩写的向量指纹与分词结果"));
      var wrap = el("div", "table-wrap");
      var t = el("table", "data-table");
      t.appendChild(el("caption", null, "缩写审计逐行结果"));
      var thead = el("thead");
      var tr = el("tr");
      ["缩写", "向量指纹", "分词", "分组"].forEach(function (h) {
        var th = el("th", null, h);
        th.setAttribute("scope", "col");
        tr.appendChild(th);
      });
      thead.appendChild(tr);
      t.appendChild(thead);
      var tbody = el("tbody");
      rows.forEach(function (r) {
        var row = el("tr");
        [r.acronym, r.fingerprint, r.tokens, r.group].forEach(function (v) {
          var td = el("td");
          if (has(v) && String(v).indexOf("[") >= 0) td.appendChild(el("code", null, String(v)));
          else td.textContent = plain(v);
          row.appendChild(td);
        });
        tbody.appendChild(row);
      });
      t.appendChild(tbody);
      wrap.appendChild(t);
      details.appendChild(wrap);
      host.appendChild(details);
    }

    if (has(acronyms.how_to_reproduce)) {
      host.appendChild(el("p", "micro", "复现："));
      host.appendChild(codeBlock(String(acronyms.how_to_reproduce)));
    }
  }

  function renderCollisions(col) {
    var host = $("collisionsBlock");
    if (!host) return;
    clear(host);
    if (!col || !col.probes) {
      host.appendChild(el("p", "quiet", "产物里没有向量碰撞记录。"));
      return;
    }

    var groups = Array.isArray(col.identical_groups) ? col.identical_groups : [];
    var p = el("p");
    p.textContent = int(col.probes) + " 个英文探针产生 " + int(col.distinct_vectors)
      + " 个不同向量"
      + (groups.length ? "；其中有 " + groups.length + " 组是完全相同的向量" : "")
      + "。";
    host.appendChild(p);

    groups.forEach(function (g) {
      var list = Array.isArray(g) ? g : [];
      if (!list.length) return;
      var line = el("p");
      line.textContent = "同一组：" + list.join("、")
        + " —— 语义检索对它们的排序一模一样，等于把 " + list.length + " 个不同概念当成一个。";
      host.appendChild(line);
    });

    if (has(col.note)) {
      host.appendChild(el("p", "micro", String(col.note)));
    }
  }

  function renderOffTopic(off) {
    var host = $("offTopicBlock");
    if (!host) return;
    clear(host);
    if (!off || !Array.isArray(off.queries) || !off.queries.length) {
      host.appendChild(el("p", "quiet", "产物里没有离题查询记录。"));
      return;
    }

    var p = el("p");
    p.textContent = "用 " + off.queries.length + " 条与导师检索完全无关的查询（做饭、天气之类）去试："
      + "空结果阈值设在 " + num(off.empty_tau, 2) + " 时，"
      + int(off.returned_empty) + " 条全部返回空"
      + (isNum(off.guarded_empty) ? "，另有兜底逻辑再挡下 " + int(off.guarded_empty) + " 条" : "")
      + "。也就是说离题查询不会被硬塞一个「最像的导师」进去。";
    host.appendChild(p);

    var rows = off.queries.map(function (q, i) {
      var sim = Array.isArray(off.top1_similarity) ? off.top1_similarity[i] : null;
      var bm = Array.isArray(off.bm25_max) ? off.bm25_max[i] : null;
      return [
        q,
        isNum(sim) ? num(sim, 3) : "—",
        isNum(bm) ? num(bm, 2) : "—"
      ];
    });

    var wrap = el("div", "table-wrap");
    var t = el("table", "data-table");
    t.appendChild(el("caption", null, "离题查询的最高相似度与最高 BM25 分"));
    var thead = el("thead");
    var tr = el("tr");
    ["离题查询", "Top-1 余弦相似度", "最高 BM25 分"].forEach(function (h, i) {
      var th = el("th", null, h);
      th.setAttribute("scope", "col");
      if (i > 0) th.className = "num";
      tr.appendChild(th);
    });
    thead.appendChild(tr);
    t.appendChild(thead);
    var tbody = el("tbody");
    rows.forEach(function (cells) {
      var row = el("tr");
      cells.forEach(function (c, i) {
        var td = el("td", i > 0 ? "num" : "cell-query");
        td.textContent = plain(c);
        row.appendChild(td);
      });
      tbody.appendChild(row);
    });
    t.appendChild(tbody);
    wrap.appendChild(t);
    host.appendChild(wrap);
  }

  function renderDegenerate(bias) {
    var host = $("degenerateBlock");
    if (!host) return;
    clear(host);
    if (!bias || typeof bias !== "object" || !Object.keys(bias).length) {
      host.appendChild(el("p", "quiet", "产物里没有退化标签统计。"));
      return;
    }

    host.appendChild(el("p", "chart-note",
      "语料里有一批记录的「研究方向」是占位标签。它们文本很短、彼此相似，"
      + "如果检索被它们吸走，Top-10 会被灌满没信息的结果。下面是实测占比。"));
    if (has(bias.definition)) host.appendChild(el("p", "micro", String(bias.definition)));

    host.appendChild(kv([
      ["占整份语料的比例", pct(bias.corpus_share)],
      ["占 test Top-10 的比例（均值）", pct(bias.test_top10_share_mean)],
      ["占 test Top-10 的比例（中位数）", pct(bias.test_top10_share_median)],
      ["语料平均文档长度", isNum(bias.corpus_mean_doc_length) ? num(bias.corpus_mean_doc_length) : "—"],
      ["test Top-10 平均文档长度", isNum(bias.test_top10_mean_doc_length) ? num(bias.test_top10_mean_doc_length) : "—"]
    ]));

    if (isNum(bias.corpus_share) && isNum(bias.test_top10_share_mean)) {
      var verdict = el("p", "micro");
      var lower = bias.test_top10_share_mean < bias.corpus_share;
      verdict.textContent = lower
        ? "Top-10 里的占比低于它在语料里的占比，说明排序没有被占位标签主导——但仍不是零，读排序结果时要记得这一层噪声。"
        : "Top-10 里的占比不低于它在语料里的占比，说明占位标签确实在挤占结果位置，这是一条需要修的已知问题。";
      host.appendChild(verdict);
    }
  }

  /* ────────────────────────── 装配 ────────────────────────── */

  function showError(message, data) {
    var loading = $("loadingPanel");
    if (loading) loading.hidden = true;
    var panel = $("errorPanel");
    var root = $("evalRoot");
    if (root) root.hidden = true;
    if (panel) panel.hidden = false;

    var detail = $("errorDetail");
    if (detail) {
      var reason = data && data.reason ? data.reason : message;
      detail.textContent = String(reason || "接口没有返回可用数据。");
      if (data && data.expected) {
        detail.textContent += "（期望的产物路径：" + data.expected + "）";
      }
    }
    var repro = $("errorRepro");
    if (repro && data && has(data.how_to_reproduce)) {
      repro.textContent = String(data.how_to_reproduce);
    }
  }

  function render(data) {
    if (!data || data.available !== true) {
      showError("评测产物还没有生成。", data);
      return;
    }

    var retrieval = data.retrieval || {};
    var methods = Array.isArray(retrieval.methods) ? retrieval.methods : [];

    LABEL_CACHE = {};
    methods.forEach(function (m) { LABEL_CACHE[m.key] = m.label || m.key; });

    safe(function () { renderSummary(data); });

    safe(function () {
      renderMethodChart("chartMethodA", "methodTableA", "noteMethodA", methods, "a", "A 类（结构化）");
      renderMethodChart("chartMethodB", "methodTableB", "noteMethodB", methods, "b", "B 类（自然语言）");
    });
    safe(function () { renderCallout(data, methods); });
    safe(function () { renderFilter(retrieval.filter || {}); });
    safe(function () {
      renderSweep(retrieval.weight_sweep || [], (data.config && data.config.chosen) || {});
    });
    safe(function () { renderLatency(retrieval.latency || {}); });
    safe(function () { renderResources(retrieval.resources || {}); });
    safe(function () { renderDirections(data.directions, data.sources); });
    safe(function () { renderDisambiguation(data.disambiguation, data.sources); });
    safe(function () { renderSignificance(data.significance); });
    safe(function () { renderFailures(retrieval.failures); });
    safe(function () { renderAcronyms(retrieval.acronyms); });
    safe(function () { renderCollisions(retrieval.collisions); });
    safe(function () { renderOffTopic(retrieval.off_topic); });
    safe(function () { renderDegenerate(retrieval.degenerate_bias); });

    var loading = $("loadingPanel");
    if (loading) loading.hidden = true;
    var root = $("evalRoot");
    if (root) root.hidden = false;

    var status = $("evalStatus");
    if (status) {
      var pending = [];
      if (!data.directions) pending.push("方向推断");
      if (!data.disambiguation) pending.push("同名消歧");
      status.textContent = "已载入 " + methods.length + " 种检索方法的产物，生成于 "
        + formatTime(data.generated_at)
        + (pending.length ? "；" + pending.join("、") + "的产物尚未入库，对应分区显示为待产出。" : "。");
    }
  }

  function boot() {
    if (!window.fetch) {
      showError("这个浏览器不支持 fetch，无法读取评测接口。");
      return;
    }
    fetch(API, { headers: { Accept: "application/json" } })
      .then(function (res) {
        if (!res.ok) throw new Error("接口返回 HTTP " + res.status);
        return res.json();
      })
      .then(function (data) { render(data); })
      .catch(function (err) {
        showError(err && err.message ? err.message : "读取评测接口失败。");
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();