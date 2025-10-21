from django.shortcuts import render

# Create your views here.


def test(request):
    return render(request, 'supplier/customer_landning.html')

def add(request):
    return render(request, 'supplier/add_customer.html')