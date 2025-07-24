from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import os
import openai
import re
import traceback

def fetch_html_with_browser(url: str) -> str:
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--window-size=1920,1080')
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.get(url)
        html = driver.page_source
    finally:
        driver.quit()
    return html

def gpt_parse_ingredients(ingredient_lines):
    client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
    prompt = (
        "Extract the quantity, unit, and ingredient name from each of these ingredient lines. "
        "Return as a JSON list of objects with keys: quantity, unit, name.\n\n"
        "Ingredients:\n" +
        "\n".join(ingredient_lines)
    )
    response = client.chat.completions.create(
        model="gpt-4.1-nano",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500,
        temperature=0
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("No content returned from GPT response")
    match = re.search(r'\[.*\]', content, re.DOTALL)
    if match:
        return json.loads(match.group(0))
    else:
        raise ValueError("No JSON found in GPT response")

def add_recipe_from_url(url: str) -> 'dict | None':
    from app import db, Recipe, app  # import app as well
    try:
        with app.app_context():
            html = fetch_html_with_browser(url)
            soup = BeautifulSoup(html, 'html.parser')
            scripts = soup.find_all('script', type='application/ld+json')
            candidates = []
            for script in scripts:
                try:
                    script_content = getattr(script, 'string', None)
                    if script_content is None:
                        script_content = script.get_text() if hasattr(script, 'get_text') else None
                    if not script_content:
                        continue
                    data = json.loads(script_content)
                    if isinstance(data, list):
                        candidates.extend(data)
                    else:
                        candidates.append(data)
                except Exception:
                    continue
            def find_recipe_obj(obj):
                if isinstance(obj, dict):
                    if 'recipeIngredient' in obj and 'recipeInstructions' in obj:
                        return obj
                    for v in obj.values():
                        found = find_recipe_obj(v)
                        if found:
                            return found
                elif isinstance(obj, list):
                    for item in obj:
                        found = find_recipe_obj(item)
                        if found:
                            return found
                return None
            recipe_obj = None
            for c in candidates:
                found = find_recipe_obj(c)
                if found:
                    recipe_obj = found
                    break
            if not recipe_obj:
                return None
            name = recipe_obj.get('name', 'Imported Recipe')
            ingredients_raw = recipe_obj.get('recipeIngredient', [])
            # Use GPT to parse ingredients
            try:
                ingredients_structured = gpt_parse_ingredients(ingredients_raw)
            except Exception as e:
                print(f"GPT ingredient parsing failed: {e}")
                # fallback: treat as unparsed
                ingredients_structured = [{'quantity': '', 'unit': '', 'name': ing} for ing in ingredients_raw]
            instructions = recipe_obj.get('recipeInstructions', '')
            if isinstance(instructions, list):
                steps = []
                for step in instructions:
                    if isinstance(step, dict) and 'text' in step:
                        steps.append(step['text'])
                    elif isinstance(step, str):
                        steps.append(step)
                instructions = '\n'.join(steps)
            image = recipe_obj.get('image', None)
            image_url = None
            if isinstance(image, list):
                image_url = image[0] if image else None
            elif isinstance(image, dict):
                image_url = image.get('url')
            else:
                image_url = image
            # Do not add to DB, just return dict for prefill
            return {
                'name': name,
                'ingredients': ingredients_structured,
                'instructions': instructions,
                'image_url': image_url
            }
    except Exception as e:
        print(f"Error importing recipe: {e}")
        traceback.print_exc()
        return None 