const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ args: ['--no-sandbox'] });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.log('PAGE ERROR:', error.message));
  page.on('requestfailed', request => console.log('REQUEST FAILED:', request.url(), request.failure().errorText));

  try {
    await page.goto('http://124.222.18.99:5174/', { waitUntil: 'networkidle0' });
    console.log('Page loaded');
  } catch (e) {
    console.log('Error loading page:', e);
  }
  
  await browser.close();
})();
