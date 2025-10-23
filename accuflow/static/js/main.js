
function navActive(id) {
    $('#'+id).addClass('active');
}

  const searchInput = document.getElementById("searchInput");
  if (searchInput){
  searchInput.addEventListener("keyup", function () {
    const filter = searchInput.value.toLowerCase();
    const rows = document.querySelectorAll(".search-area");

    rows.forEach((row) => {
      const text = row.innerText.toLowerCase();
      row.style.display = text.includes(filter) ? "" : "none";
    });
  });
}



  const searchBtn = document.getElementById('searchBtn');
  const searchWrapper = document.getElementById('searchWrapper');

  let expanded = false;
if (searchBtn){
searchBtn.addEventListener('click', (e) => {
  e.stopPropagation(); 
  expanded = !expanded;

  if (expanded) {
    // Make input visible first
    searchInput.classList.remove('hidden');

    // Small delay to allow transition
    setTimeout(() => {
      searchWrapper.classList.remove('w-10');
      searchWrapper.classList.add('w-64');
      searchInput.classList.remove('w-0', 'opacity-0');
      searchInput.classList.add('w-full', 'opacity-100');
      searchInput.focus();
    }, 10);

  } else {
    // Start collapse
    searchWrapper.classList.remove('w-64');
    searchWrapper.classList.add('w-10');
    searchInput.classList.remove('w-full', 'opacity-100');
    searchInput.classList.add('w-0', 'opacity-0');

    // Wait for transition to finish before hiding
    setTimeout(() => {
      searchInput.classList.add('hidden');
      searchInput.value = '';
    }, 300); // match transition duration
  }
});

// Collapse when clicking outside
document.addEventListener('click', (e) => {
  if (!searchWrapper.contains(e.target) && expanded) {
    expanded = false;
    searchWrapper.classList.remove('w-64');
    searchWrapper.classList.add('w-10');
    searchInput.classList.remove('w-full', 'opacity-100');
    searchInput.classList.add('w-0', 'opacity-0');
    setTimeout(() => {
      searchInput.classList.add('hidden');
      searchInput.value = '';
    }, 300);
  }
});
}
selectedTag = []
$('td').on('click', function() {

  if ($(this).find('button').length > 0) return;
  var $tr = $(this).closest('tr');
  $tr.toggleClass('hover:bg-blue-100 odd:bg-blue-100 even:bg-blue-100');

  var rowId = $tr.data('id'); 
  if ($tr.hasClass('hover:bg-blue-100 odd:bg-blue-100 even:bg-blue-100')) {
    if (!selectedTag.includes(rowId)) selectedTag.push(rowId);
  } else {
    selectedTag = selectedTag.filter(id => id !== rowId);
  }
  
});