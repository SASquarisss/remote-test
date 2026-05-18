import puppeteer from 'puppeteer';

(async () => {
  const browser = await puppeteer.launch({ 
    executablePath: '/usr/bin/chromium',
    args: ['--no-sandbox', '--disable-setuid-sandbox'] 
  });
  const page = await browser.newPage();
  
  page.on('console', msg => console.log('PAGE LOG:', msg.text()));
  page.on('pageerror', error => console.error('PAGE ERROR:', error.message));
  page.on('requestfailed', request => console.error('REQUEST FAILED:', request.url(), request.failure().errorText));
  
  await page.goto('http://localhost:5174/', { waitUntil: 'networkidle2' });
  
  await browser.close();
})();
