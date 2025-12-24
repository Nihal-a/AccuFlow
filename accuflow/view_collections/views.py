import datetime
import json
from django.shortcuts import render,redirect, get_object_or_404
from core.models import Commissions,Expenses,Godowns
from django.views import View
from django.views.generic.edit import DeleteView
from django.http import JsonResponse
from django.utils.dateparse import parse_date

from core.views import getClient

class ViewCOllectionsView(View):
    def get(self,request):
        
        return render(request,'view_collections/view_collections.html')
    
   