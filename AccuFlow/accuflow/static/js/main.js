
function navActive(id) {
  $('.nav-link').removeClass('active');
    $('#'+id).addClass('active');
}
const searchInput = document.getElementById("searchInput");

if (searchInput) {
  searchInput.addEventListener("keyup", function () {
    const filter = searchInput.value.toLowerCase();
    const rows = document.querySelectorAll("tbody tr"); 
    console.log(filter)
    rows.forEach((row) => {
      const text = row.querySelector(".search-area") 
        ? row.querySelectorAll(".search-area") 
        : [];

      let rowText = "";
      text.forEach((cell) => {
        rowText += cell.innerText.toLowerCase() + " ";
      });

      row.style.display = rowText.includes(filter) ? "" : "none";
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




function isBackAvailable() {
  if (document.referrer === "") return false;
  if (!document.referrer.startsWith("http://127.0.0.1:8000")) return false;

  return true;
}

function goBack() {
  if (isBackAvailable()) {
    history.go(-1);
  }
}

function goNext() {
  history.go(1);
}

$(document).ready(function () {
  if (!isBackAvailable()) {
    $("#back-button").addClass("disabled-btn");
  }
});


function getToken(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
      const cookies = document.cookie.split(';');
      for (let i = 0; i < cookies.length; i++) {
          const cookie = cookies[i].trim();
          if (cookie.substring(0, name.length + 1) === (name + '=')) {
              cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
              break;
          }
      }
  }
  return cookieValue;
}
const csrftoken = getToken('csrftoken')



let isFormDirty = false;
const forms = document.getElementsByTagName("form");

if (forms.length > 0) {
  // Track input changes in all forms
  $("form :input").on("input change", function () {
    isFormDirty = true;
  });

  // When any form is submitted, reset the flag
  Array.from(forms).forEach((form) => {
    form.addEventListener("submit", function () {
      isFormDirty = false;
    });
  });

  // Warn when trying to leave or reload the page
  window.addEventListener("beforeunload", function (e) {
    if (isFormDirty) {
      e.preventDefault();
      e.returnValue = "You have unsaved changes. Do you really want to leave?";
    }
  });
}

function countryCode(){
  var countrySelect = document.getElementById('countryCode')
  $(countrySelect).html(`
      <option value="+971">🇦🇪 +971 (UAE)</option>
                <option value="+966">🇸🇦 +966 (Saudi Arabia)</option>
                <option value="+974">🇶🇦 +974 (Qatar)</option>
                <option value="+965">🇰🇼 +965 (Kuwait)</option>
                <option value="+968">🇴🇲 +968 (Oman)</option>
                <option value="+973">🇧🇭 +973 (Bahrain)</option>
                <option value="+962">🇯🇴 +962 (Jordan)</option>
                <option value="+961">🇱🇧 +961 (Lebanon)</option>
                <option value="+20">🇪🇬 +20 (Egypt)</option>
                <option value="+963">🇸🇾 +963 (Syria)</option>
                <option value="+967">🇾🇪 +967 (Yemen)</option>
                <option value="+218">🇱🇾 +218 (Libya)</option>
                <option value="+212">🇲🇦 +212 (Morocco)</option>
                <option value="+213">🇩🇿 +213 (Algeria)</option>
                <option value="+249">🇸🇩 +249 (Sudan)</option>

                <option value="+91" selected>🇮🇳 +91 (India)</option>
                <option value="+1">🇺🇸 +1 (USA)</option>
                <option value="+44">🇬🇧 +44 (UK)</option>
                <option value="+61">🇦🇺 +61 (Australia)</option>
                <option value="+94">🇱🇰 +94 (Sri Lanka)</option>
                <option value="+880">🇧🇩 +880 (Bangladesh)</option>
                <option value="+92">🇵🇰 +92 (Pakistan)</option>
                <option value="+81">🇯🇵 +81 (Japan)</option>
                <option value="+86">🇨🇳 +86 (China)</option>
    `)
}

if ($('#date').length){
$('#date').val(new Date().toISOString().split('T')[0]);
} 