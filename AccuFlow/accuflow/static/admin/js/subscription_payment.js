(function ($) {
    $(document).ready(function () {
        $('#id_plan').change(function () {
            var planId = $(this).val();
            if (planId) {
                // Fetch price from API
                $.ajax({
                    url: '/api/get-plan-details/' + planId + '/',
                    type: 'GET',
                    success: function (data) {
                        if (data.price !== undefined) {
                            $('#id_amount').val(data.price);
                        }
                    },
                    error: function (error) {
                        console.error('Error fetching plan price:', error);
                    }
                });
            } else {
                $('#id_amount').val('');
            }
        });
    });
})(django.jQuery);
