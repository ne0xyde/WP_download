import os


base_url = 'https://iscps.info'
user = os.environ.get('WP_USER')
password = os.environ.get('WP_PSW')

''' 
    <!-- wp:paragraph --><p></p><!-- /wp:paragraph -->
    <!-- wp:html --><!-- /wp:html -->
    <!-- wp:group --><!-- /wp:group -->
'''

data = '''
<!-- wp:html -->
    <style>
        /* Основные стили для кнопки */
        .download-button {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 10px 20px;
            font-size: 16px;
            font-weight: bold;
            color: white;
            background: linear-gradient(to right, #00c6ff, #0072ff);
            border: none;
            border-radius: 30px;
            text-decoration: none;
            cursor: pointer;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }

        /* Добавляем эффект при наведении */
        .download-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 8px rgba(0, 0, 0, 0.2);
        }

        /* Иконка "стрелка вниз" */
        .icon {
            margin-right: 8px;
            margin-left: 8px;
        }
    </style>
    <div class="button-container" style="display: flex; justify-content: center; align-items: center">
        <a href="{product_link}" class="download-button">
                <span class="icon">⤋</span>
                <span class="text">FREE DOWNLOAD</span>
                <span class="icon">⤋</span>
        </a>
    </div>
<!-- /wp:html -->
<!-- wp:paragraph -->
<p>{description}</p>
<!-- /wp:paragraph -->

'''
