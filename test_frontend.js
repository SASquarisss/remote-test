const fs = require('fs');
const data = JSON.parse(fs.readFileSync('visualization/data/test_data.json', 'utf8'));
console.log(Object.keys(data));
