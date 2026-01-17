
from django.views import View
from django.shortcuts import render

class ChangePassView(View):
    def get(self, request):
        return render(request, 'change_pass/change_pass.html')
