// Upload + Drag & Drop
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
dropZone.onclick = () => fileInput.click();
dropZone.ondragover = e => { e.preventDefault(); dropZone.classList.add('border-blue-500'); };
dropZone.ondragleave = () => dropZone.classList.remove('border-blue-500');
dropZone.ondrop = e => { e.preventDefault(); dropZone.classList.remove('border-blue-500'); uploadFiles(e.dataTransfer.files); };
fileInput.onchange = () => uploadFiles(fileInput.files);

function uploadFiles(files) {
  const form = new FormData();
  for (let f of files) form.append('files', f);
  fetch('/upload', { method: 'POST', body: form })
    .then(r => r.json())
    .then(() => location.reload());
}

// Prévisualisation PDF
function openPreview(fileId) {
  document.getElementById('pdfViewer').src = `/preview/${fileId}`;
  document.getElementById('pdfModal').classList.remove('hidden');
}
function closeModal() {
  document.getElementById('pdfModal').classList.add('hidden');
  document.getElementById('pdfViewer').src = '';
}

// Autres fonctions (delete, share, search) identiques à avant
function deleteFile(id, el) {
  if (!confirm('Supprimer ?')) return;
  fetch(`/delete/${id}`, {method: 'DELETE'}).then(() => {
    el.closest('. abroad').style.opacity = '0';
    setTimeout(() => location.reload(), 400);
  });
}
function copyShare(url) {
  navigator.clipboard.writeText(url); alert('Lien copié !');
}
document.getElementById('searchInput').oninput = function() {
  const term = this.value.toLowerCase();
  document.querySelectorAll('.file-card').forEach(c => {
    c.style.display = c.dataset.name.includes(term) ? '' : 'none';
  });
};