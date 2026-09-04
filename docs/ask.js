const $ = id => document.getElementById(id);

$("q").focus();

function reset(){
  $("results").hidden = true;
  $("q").value = "";
  $("list").innerHTML = "";
  $("q").focus();
}

$("again").addEventListener("click", reset);

let works = null;

async function load(){
  if (works) return works;
  const res = await fetch("data/popular.json");
  if (!res.ok) throw new Error("data unavailable");
  works = (await res.json()).works;
  return works;
}

const fmt = n => n.toLocaleString("en-US");

function render(items){
  $("list").innerHTML = items.map(b => {
    const bits = [];
    if (b.year)   bits.push(b.year);
    if (b.pages)  bits.push(b.pages + " pages");
    if (b.rating) bits.push(b.rating + "\u2605 from " + fmt(b.ratings) + " ratings");
    return '<li><div><div class="bt">' + b.title +
           '</div><div class="bm">' + bits.join(" \u00b7 ") + '</div></div></li>';
  }).join("");
}

$("form").addEventListener("submit", async e => {
  e.preventDefault();
  if (!$("q").value.trim()) return;

  $("results").hidden = false;
  $("note").textContent = "Loading\u2026";
  $("list").innerHTML = "";

  try {
    const all = await load();
    $("note").textContent = "";
    render(all.slice(0, 10));
  } catch (err) {
    $("note").textContent = "Couldn't load the catalog. Try reloading the page.";
  }
});
