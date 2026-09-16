from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic.base import RedirectView, TemplateView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('shop_grid/', views.shop_grid, name='shop_grid'),
    path('shop/', views.shop_grid, name='shop'),
    path('category/<path:slug_path>/', views.category_page, name='category_page'),
    path('quick-view/<int:product_id>/', views.quick_view, name='quick_view'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('partners/', views.partner_list, name='partner_list'),
    path('union_list/', views.union_list, name='union_list'),
    path('dealers/', views.dealer_list, name='dealer_list'),
    path('sellers/', views.seller_list, name='seller_list'),
    path('partner/<slug:slug>/', views.partner_detail, name='partner_detail'),
    path('page/<slug:slug>/', views.page_detail, name='page_detail'),
    path('store/page/<slug:slug>/', RedirectView.as_view(pattern_name='page_detail', permanent=True)),
    path('landing/<slug:slug>/', views.landing_page, name='landing_page'),
    path('blog/', views.blog_list, name='blog_list'),
    path('blog/<slug:slug>/', views.blog_detail, name='blog_detail'),
    path('apply-coupon/', views.apply_coupon, name='apply_coupon'),
    path('order/<int:order_id>/print/', views.public_print_invoice, name='public_print_invoice'),
    path('order/<int:order_id>/pdf/', views.invoice_pdf, name='invoice_pdf'),
    path('contact/', views.contact, name='contact'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='store/password_reset.html',
        email_template_name='store/password_reset_email.html',
        subject_template_name='store/password_reset_subject.txt',
        success_url='/password-reset/done/',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='store/password_reset_done.html',
    ), name='password_reset_done'),
    path('password-reset/confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='store/password_reset_confirm.html',
        success_url='/password-reset/complete/',
    ), name='password_reset_confirm'),
    path('password-reset/complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='store/password_reset_complete.html',
    ), name='password_reset_complete'),
    path('add-to-cart/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('buy-now/<int:product_id>/', views.buy_now, name='buy_now'),
    path('cart/', views.cart_view, name='cart'),
    path('remove-from-cart/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('update-cart/<int:item_id>/', views.update_cart, name='update_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('order-confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/custom-domain/', views.dashboard_custom_domain, name='dashboard_custom_domain'),
    path('dashboard/become-seller/', views.dashboard_become_seller, name='dashboard_become_seller'),
    path('dashboard/products/', views.dashboard_products, name='dashboard_products'),
    path('dashboard/products/add/', views.dashboard_product_create, name='dashboard_product_create'),
    path('dashboard/products/edit/<int:pk>/', views.dashboard_product_edit, name='dashboard_product_edit'),
    path('dashboard/products/delete/<int:pk>/', views.dashboard_product_delete, name='dashboard_product_delete'),
    path('dashboard/products/duplicate/<int:pk>/', views.dashboard_product_duplicate, name='dashboard_product_duplicate'),
    path('dashboard/products/export/csv/', views.dashboard_products_export_csv, name='dashboard_products_export_csv'),
    path('dashboard/products/export/pdf/', views.dashboard_products_export_pdf, name='dashboard_products_export_pdf'),
    path('dashboard/products/bulk-delete/', views.dashboard_product_bulk_delete, name='dashboard_product_bulk_delete'),
    path('dashboard/products/trash/', views.dashboard_trash_list, name='dashboard_trash_list'),
    path('dashboard/products/trash/restore/', views.dashboard_trash_restore, name='dashboard_trash_restore'),
    path('dashboard/products/trash/restore-all/', views.dashboard_trash_restore_all, name='dashboard_trash_restore_all'),
    path('dashboard/products/trash/empty/', views.dashboard_trash_empty, name='dashboard_trash_empty'),
    path('dashboard/profile/', views.dashboard_profile_edit, name='dashboard_profile_edit'),
    path('dashboard/orders/', views.dashboard_orders, name='dashboard_orders'),
    path('dashboard/my-orders/', views.customer_orders, name='customer_orders'),
    path('dashboard/my-orders/<int:order_id>/', views.customer_order_detail, name='customer_order_detail'),
    path('dashboard/custom-orders/', views.dashboard_custom_orders, name='dashboard_custom_orders'),
    path('dashboard/custom-orders/add/', views.dashboard_custom_order_create, name='dashboard_custom_order_create'),
    path('dashboard/custom-orders/edit/<int:pk>/', views.dashboard_custom_order_edit, name='dashboard_custom_order_edit'),
    path('dashboard/custom-orders/delete/<int:pk>/', views.dashboard_custom_order_delete, name='dashboard_custom_order_delete'),
    path('dashboard/addresses/', views.dashboard_addresses, name='dashboard_addresses'),
    path('dashboard/addresses/add/', views.dashboard_address_add, name='dashboard_address_add'),
    path('dashboard/addresses/edit/<int:pk>/', views.dashboard_address_edit, name='dashboard_address_edit'),
    path('dashboard/addresses/delete/<int:pk>/', views.dashboard_address_delete, name='dashboard_address_delete'),
    path('dashboard/addresses/set-default/<int:pk>/', views.dashboard_address_set_default, name='dashboard_address_set_default'),
    path('dashboard/change-password/', auth_views.PasswordChangeView.as_view(
        template_name='store/change_password.html',
        success_url='/dashboard/',
    ), name='change_password'),
    path('cancel-order/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('add-review/<int:product_id>/', views.add_review, name='add_review'),
    path('edit-review/<int:review_id>/', views.edit_review, name='edit_review'),
    path('delete-review/<int:review_id>/', views.delete_review, name='delete_review'),
    path('dashboard/reviews/', views.dashboard_reviews, name='dashboard_reviews'),
    path('dashboard/partner/menu/', views.dashboard_menu_list, name='dashboard_menu_list'),
    path('dashboard/partner/menu/add/', views.dashboard_menu_add, name='dashboard_menu_add'),
    path('dashboard/partner/menu/edit/<int:pk>/', views.dashboard_menu_edit, name='dashboard_menu_edit'),
    path('dashboard/partner/menu/delete/<int:pk>/', views.dashboard_menu_delete, name='dashboard_menu_delete'),
    path('dashboard/partner/side-banners/', views.dashboard_side_banners, name='dashboard_side_banners'),
    path('dashboard/partner/side-banners/add/', views.dashboard_side_banner_add, name='dashboard_side_banner_add'),
    path('dashboard/partner/side-banners/edit/<int:pk>/', views.dashboard_side_banner_edit, name='dashboard_side_banner_edit'),
    path('dashboard/partner/side-banners/delete/<int:pk>/', views.dashboard_side_banner_delete, name='dashboard_side_banner_delete'),
    path('dashboard/sellers/', views.dashboard_sellers, name='dashboard_sellers'),
    path('dashboard/sellers/add/', views.dashboard_seller_add, name='dashboard_seller_add'),
    path('dashboard/union-agents/', views.dashboard_union_agents, name='dashboard_union_agents'),
    path('dashboard/union-agents/add/', views.dashboard_union_agent_add, name='dashboard_union_agent_add'),

    # Partner Sliders
    path('dashboard/sliders/', views.dashboard_slider_list, name='dashboard_slider_list'),
    path('dashboard/sliders/add/', views.dashboard_slider_add, name='dashboard_slider_add'),
    path('dashboard/sliders/edit/<int:pk>/', views.dashboard_slider_edit, name='dashboard_slider_edit'),
    path('dashboard/sliders/delete/<int:pk>/', views.dashboard_slider_delete, name='dashboard_slider_delete'),

    # Payment
    path('payment/<int:order_id>/', views.payment_init, name='payment_init'),
    path('payment/<int:order_id>/process/', views.payment_process, name='payment_process'),
    path('payment/<int:order_id>/success/', views.payment_success, name='payment_success'),
    path('payment/<int:order_id>/fail/', views.payment_fail, name='payment_fail'),
    path('payment/<int:order_id>/cancel/', views.payment_cancel, name='payment_cancel'),
    path('payment/<int:order_id>/manual/', views.payment_manual, name='payment_manual'),

    # Sitemap & robots
    path('sitemap.xml', views.sitemap_view, name='sitemap'),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain'), name='robots'),

    # Wallet
    path('dashboard/wallet/', views.dashboard_wallet, name='dashboard_wallet'),
    path('dashboard/wallet/transactions/', views.dashboard_wallet_transactions, name='dashboard_wallet_transactions'),
    path('dashboard/wallet/withdraw/', views.dashboard_withdraw, name='dashboard_withdraw'),
    path('dashboard/wallet/withdrawals/', views.dashboard_withdrawal_list, name='dashboard_withdrawal_list'),
    path('dashboard/wallet/payout-methods/', views.dashboard_payout_methods, name='dashboard_payout_methods'),
    path('dashboard/wallet/payout-methods/delete/<int:pk>/', views.dashboard_payout_method_delete, name='dashboard_payout_method_delete'),

    # Feature 1: Wishlist
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/add/<int:product_id>/', views.wishlist_add, name='wishlist_add'),
    path('wishlist/remove/<int:item_id>/', views.wishlist_remove, name='wishlist_remove'),

    # Feature 3: Compare
    path('compare/', views.compare_view, name='compare'),
    path('compare/add/<int:product_id>/', views.compare_add, name='compare_add'),
    path('compare/remove/<int:product_id>/', views.compare_remove, name='compare_remove'),
    path('compare/clear/', views.compare_clear, name='compare_clear'),

    path('dashboard/toggle-products/', views.dashboard_toggle_products, name='dashboard_toggle_products'),
    path('dashboard/toggle-all-products-section/', views.dashboard_toggle_all_products_section, name='dashboard_toggle_all_products_section'),
    path('dashboard/toggle-random-products-section/', views.dashboard_toggle_random_products_section, name='dashboard_toggle_random_products_section'),
    path('dashboard/toggle-slider/', views.dashboard_toggle_slider, name='dashboard_toggle_slider'),

    # POS (Point of Sale)
    path('dashboard/pos/', views.pos_dashboard, name='pos_dashboard'),
    path('dashboard/pos/orders/', views.pos_order_list, name='pos_order_list'),
    path('dashboard/pos/orders/<int:pk>/', views.pos_order_detail, name='pos_order_detail'),
    path('dashboard/pos/orders/<int:pk>/refund/', views.pos_order_refund, name='pos_order_refund'),
    path('dashboard/pos/orders/<int:pk>/delete/', views.pos_order_delete, name='pos_order_delete'),
    path('dashboard/pos/create/', views.pos_order_create, name='pos_order_create'),
    path('dashboard/pos/products/search/', views.pos_product_search, name='pos_product_search'),
    path('dashboard/pos/report/', views.pos_daily_report, name='pos_daily_report'),

    # Medicine POS
    path('dashboard/medicine-pos/', views.medicine_pos_dashboard, name='medicine_pos_dashboard'),
    path('dashboard/medicine-pos/create/', views.medicine_pos_order_create, name='medicine_pos_order_create'),
    path('dashboard/medicine-pos/products/search/', views.medicine_pos_product_search, name='medicine_pos_product_search'),
    path('dashboard/medicine-pos/orders/', views.medicine_pos_order_list, name='medicine_pos_order_list'),
    path('dashboard/medicine-pos/orders/<int:pk>/', views.medicine_pos_order_detail, name='medicine_pos_order_detail'),
    path('dashboard/medicine-pos/orders/<int:pk>/refund/', views.medicine_pos_order_refund, name='medicine_pos_order_refund'),
    path('dashboard/medicine-pos/orders/<int:pk>/delete/', views.medicine_pos_order_delete, name='medicine_pos_order_delete'),
    path('dashboard/medicine-pos/report/', views.medicine_pos_daily_report, name='medicine_pos_daily_report'),
    path('dashboard/medicine-pos/subscription/', views.medicine_subscription_page, name='medicine_subscription_page'),
    path('dashboard/medicine-pos/request-product/', views.medicine_request_product, name='medicine_request_product'),
    path('dashboard/medicine-pos/wallet-recharge/', views.wallet_recharge, name='wallet_recharge'),
    path('dashboard/medicine-pos/inventory/toggle/', views.medicine_inventory_toggle, name='medicine_inventory_toggle'),
    path('dashboard/medicine-pos/inventory/', views.medicine_inventory_list, name='medicine_inventory_list'),
    path('dashboard/medicine-pos/inventory/adjust/<int:pk>/', views.medicine_inventory_adjust, name='medicine_inventory_adjust'),
    path('dashboard/medicine-pos/inventory/log/', views.medicine_inventory_log, name='medicine_inventory_log'),
    path('dashboard/medicine-pos/inventory/log/export/', views.medicine_inventory_log_export, name='medicine_inventory_log_export'),
    path('dashboard/medicine-pos/inventory/log/order/', views.medicine_pos_company_order, name='medicine_pos_company_order'),
    path('dashboard/medicine-pos/order/draft/save/', views.medicine_pos_order_draft_save, name='medicine_pos_order_draft_save'),
    path('dashboard/medicine-pos/order/export/', views.medicine_pos_company_order_export, name='medicine_pos_company_order_export'),
    path('dashboard/medicine-pos/inventory/bulk/', views.medicine_inventory_bulk_update, name='medicine_inventory_bulk_update'),

    # Feature 4: Notifications
    path('dashboard/notifications/', views.dashboard_notifications, name='dashboard_notifications'),
    path('dashboard/notifications/read/<int:pk>/', views.notification_read, name='notification_read'),
    path('dashboard/notifications/read-all/', views.notification_read_all, name='notification_read_all'),

    # Feature 6: Refunds
    path('order/<int:order_id>/request-refund/', views.request_refund, name='request_refund'),
    path('dashboard/refunds/', views.dashboard_refunds, name='dashboard_refunds'),

    # Feature 7: Analytics
    path('dashboard/analytics/', views.dashboard_analytics, name='dashboard_analytics'),
    path('dashboard/analytics/data/', views.dashboard_analytics_data, name='dashboard_analytics_data'),

    # Feature 8: Bulk upload
    path('dashboard/products/bulk-upload/', views.dashboard_product_bulk_upload, name='dashboard_product_bulk_upload'),
    path('dashboard/products/bulk-upload/progress/<uuid:batch_id>/', views.dashboard_bulk_import_progress, name='dashboard_bulk_import_progress'),

    # Feature: Messaging
    path('messages/', views.customer_message_list, name='customer_message_list'),
    path('messages/new/<int:partner_id>/', views.customer_message_create, name='customer_message_create'),
    path('messages/<int:conv_id>/', views.customer_message_detail, name='customer_message_detail'),
    path('dashboard/messages/', views.partner_message_list, name='partner_message_list'),
    path('dashboard/messages/<int:conv_id>/', views.partner_message_detail, name='partner_message_detail'),
    path('dashboard/admin/messages/', views.admin_message_list, name='admin_message_list'),
    path('dashboard/admin/messages/<int:conv_id>/', views.admin_message_detail, name='admin_message_detail'),
    path('dashboard/admin/messages/broadcast/', views.admin_broadcast_create, name='admin_broadcast_create'),

    # Product Q&A
    path('product/<int:product_id>/ask-question/', views.product_ask_question, name='product_ask_question'),
    path('qa/<int:qa_id>/answer/', views.product_answer_question, name='product_answer_question'),
    path('dashboard/qa/', views.partner_qa_list, name='partner_qa_list'),

    # Feature: Support Tickets
    path('dashboard/tickets/', views.dashboard_tickets, name='dashboard_tickets'),
    path('dashboard/tickets/create/', views.dashboard_ticket_create, name='dashboard_ticket_create'),
    path('dashboard/tickets/<int:pk>/', views.dashboard_ticket_detail, name='dashboard_ticket_detail'),
    path('dashboard/admin/tickets/', views.admin_ticket_list, name='admin_ticket_list'),
    path('dashboard/admin/tickets/<int:pk>/', views.admin_ticket_detail, name='admin_ticket_detail'),

    # API
    path('api/', include('store.api_urls')),

    # Live site URL compatibility aliases
    path('vandor_list_all/', RedirectView.as_view(pattern_name='partner_list', permanent=True)),
    path('dealer_list/', RedirectView.as_view(pattern_name='dealer_list', permanent=True)),
    path('selear_list/', RedirectView.as_view(pattern_name='seller_list', permanent=True)),
    path('seller_list/', RedirectView.as_view(pattern_name='seller_list', permanent=True)),
    path('openuser_registration/', RedirectView.as_view(pattern_name='register', permanent=True)),
    path('search/', views.search_view, name='search'),
    path('subscribe/', views.newsletter_subscribe, name='newsletter_subscribe'),
    path('Health/Discount/Card/', views.discount_card, name='discount_card'),
    path('manu_product_list/', views.manufacturer_products, name='manufacturer_products'),
    path('admin/upload-image/', views.admin_upload_image, name='admin_upload_image'),
    path('terms_and_conditions/', views.site_page, {'slug': 'terms-conditions', 'fallback_template': 'store/terms_and_conditions.html'}, name='terms_and_conditions'),
    path('return_refund/', views.site_page, {'slug': 'return-refund-policy', 'fallback_template': 'store/return_refund.html'}, name='return_refund'),
    path('company_policy/', views.site_page, {'slug': 'company-policy', 'fallback_template': 'store/company_policy.html'}, name='company_policy'),
]
