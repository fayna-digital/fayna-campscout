
var KADRY_VALID = {};

(function() {
    // Helper for PESEL/NIP checksums
    function calculateChecksum(value, weights) {
        var sum = 0;
        for (var i = 0; i < value.length; i++) {
            sum += parseInt(value.charAt(i), 10) * weights[i];
        }
        return sum;
    }

    // PESEL validation
    KADRY_VALID.pesel = function(v) {
        if (typeof v !== 'string' || !/^\d{11}$/.test(v)) {
            return { ok: false, code: 'FORMAT' };
        }

        var weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3, 1];
        var sum = calculateChecksum(v, weights);
        if (sum % 10 !== 0) {
            return { ok: false, code: 'CHECKSUM' };
        }

        var year = parseInt(v.substring(0, 2), 10);
        var month = parseInt(v.substring(2, 4), 10);
        var day = parseInt(v.substring(4, 6), 10);

        var century = 1900;
        if (month > 80) {
            century = 2200;
            month -= 80;
        } else if (month > 60) {
            century = 2100;
            month -= 60;
        } else if (month > 40) {
            century = 2000;
            month -= 40;
        } else if (month > 20) {
            century = 1800;
            month -= 20;
        }

        year = century + year;

        if (month < 1 || month > 12 || day < 1 || day > 31) {
            return { ok: false, code: 'DATE_INVALID' };
        }

        var date = new Date(year, month - 1, day);
        if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
            return { ok: false, code: 'DATE_INVALID' };
        }

        return { ok: true };
    };

    // PESEL birth date extraction
    KADRY_VALID.peselBirthDate = function(v) {
        if (typeof v !== 'string' || !/^\d{11}$/.test(v)) {
            return { ok: false, code: 'FORMAT' };
        }

        var year = parseInt(v.substring(0, 2), 10);
        var month = parseInt(v.substring(2, 4), 10);
        var day = parseInt(v.substring(4, 6), 10);

        var century = 1900;
        if (month > 80) {
            century = 2200;
            month -= 80;
        } else if (month > 60) {
            century = 2100;
            month -= 60;
        } else if (month > 40) {
            century = 2000;
            month -= 40;
        } else if (month > 20) {
            century = 1800;
            month -= 20;
        }

        year = century + year;

        if (month < 1 || month > 12 || day < 1 || day > 31) {
            return { ok: false, code: 'DATE_INVALID' };
        }

        var date = new Date(year, month - 1, day);
        if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) {
            return { ok: false, code: 'DATE_INVALID' };
        }

        var yearStr = String(year);
        var monthStr = (month < 10 ? '0' : '') + month;
        var dayStr = (day < 10 ? '0' : '') + day;

        return { ok: true, date: yearStr + '-' + monthStr + '-' + dayStr };
    };

    // NIP validation
    KADRY_VALID.nip = function(v) {
        if (typeof v !== 'string') {
            v = String(v); // Convert to string if not already
        }
        v = v.replace(/[^0-9]/g, ''); // Remove non-digits

        if (!/^\d{10}$/.test(v)) {
            return { ok: false, code: 'FORMAT' };
        }

        var weights = [6, 5, 7, 2, 3, 4, 5, 6, 7];
        var sum = calculateChecksum(v.substring(0, 9), weights);
        var controlDigit = parseInt(v.charAt(9), 10);

        if (sum % 11 !== controlDigit) {
            return { ok: false, code: 'CHECKSUM' };
        }

        return { ok: true };
    };

    // IBAN validation (PL and UA share the same algorithm)
    function validateIban(iban) {
        iban = iban.toUpperCase().replace(/[^A-Z0-9]/g, '');

        if (iban.length < 15 || iban.length > 34) { // Typical range, not strict for specific country
            return { ok: false, code: 'LENGTH' };
        }

        var rearranged = iban.substring(4) + iban.substring(0, 4);
        var numeric = '';
        for (var i = 0; i < rearranged.length; i++) {
            var char = rearranged.charAt(i);
            if (char >= 'A' && char <= 'Z') {
                numeric += (char.charCodeAt(0) - 'A'.charCodeAt(0) + 10);
            } else {
                numeric += char;
            }
        }

        // Modulo 97-10 calculation
        var remainder = 0;
        for (var j = 0; j < numeric.length; j++) {
            remainder = (remainder * 10 + parseInt(numeric.charAt(j), 10)) % 97;
        }

        if (remainder !== 1) {
            return { ok: false, code: 'CHECKSUM' };
        }

        return { ok: true };
    }

    KADRY_VALID.ibanPL = function(v) {
        var iban = String(v).toUpperCase().replace(/[^A-Z0-9]/g, '');
        if (iban.length === 26 && /^\d{26}$/.test(iban)) { // If only digits, assume PL prefix
            iban = 'PL' + iban;
        }
        if (!/^PL\d{26}$/.test(iban)) {
            return { ok: false, code: 'FORMAT' };
        }
        return validateIban(iban);
    };

    // RNOPPP validation
    KADRY_VALID.rnokpp = function(v) {
        if (typeof v !== 'string') {
            v = String(v);
        }
        v = v.replace(/[^0-9]/g, '');

        if (!/^\d{10}$/.test(v)) {
            return { ok: false, code: 'FORMAT' };
        }

        var weights = [-1, 5, 7, 9, 4, 6, 10, 5, 7];
        var sum = calculateChecksum(v.substring(0, 9), weights);
        var controlDigit = parseInt(v.charAt(9), 10);

        var remainder = sum % 11;
        if (remainder === 10) {
            remainder = 0;
        }

        if (remainder !== controlDigit) {
            return { ok: false, code: 'CHECKSUM' };
        }

        return { ok: true };
    };

    KADRY_VALID.ibanUA = function(v) {
        var iban = String(v).toUpperCase().replace(/[^A-Z0-9]/g, '');
        if (!/^UA\d{27}$/.test(iban)) {
            return { ok: false, code: 'FORMAT' };
        }
        return validateIban(iban);
    };

    // Transliteration
    KADRY_VALID.translitUaToLat = function(s) {
        if (typeof s !== 'string') {
            return '';
        }

        var result = '';
        var words = s.split(/(\s+)/); // Split by whitespace, keeping whitespace

        for (var w = 0; w < words.length; w++) {
            var word = words[w];
            if (word.trim() === '') {
                result += word;
                continue;
            }

            var transliteratedWord = '';
            for (var i = 0; i < word.length; i++) {
                var char = word.charAt(i);
                var nextChar = (i + 1 < word.length) ? word.charAt(i + 1) : '';
                var isFirstCharOfWord = (i === 0);

                var lowerChar = char.toLowerCase();
                var isUpperCase = (char === char.toUpperCase() && char !== char.toLowerCase()); // Check if it's an uppercase letter

                var replacement = '';

                // Special cases for 'зг'
                if (lowerChar === 'з' && nextChar.toLowerCase() === 'г') {
                    replacement = isUpperCase ? 'Zgh' : 'zgh';
                    transliteratedWord += replacement;
                    i++; // Skip next char 'г'
                    continue;
                }

                switch (lowerChar) {
                    case 'є':
                        replacement = isFirstCharOfWord ? 'ye' : 'ie';
                        break;
                    case 'ї':
                        replacement = isFirstCharOfWord ? 'yi' : 'i';
                        break;
                    case 'й':
                        replacement = isFirstCharOfWord ? 'y' : 'i';
                        break;
                    case 'ю':
                        replacement = isFirstCharOfWord ? 'yu' : 'iu';
                        break;
                    case 'я':
                        replacement = isFirstCharOfWord ? 'ya' : 'ia';
                        break;
                    case 'ж':
                        replacement = 'zh';
                        break;
                    case 'х':
                        replacement = 'kh';
                        break;
                    case 'ц':
                        replacement = 'ts';
                        break;
                    case 'ч':
                        replacement = 'ch';
                        break;
                    case 'ш':
                        replacement = 'sh';
                        break;
                    case 'щ':
                        replacement = 'shch';
                        break;
                    case 'г':
                        replacement = 'h';
                        break;
                    case 'ґ':
                        replacement = 'g';
                        break;
                    case 'и':
                        replacement = 'y';
                        break;
                    case 'а': replacement = 'a'; break;
                    case 'б': replacement = 'b'; break;
                    case 'в': replacement = 'v'; break;
                    case 'д': replacement = 'd'; break;
                    case 'е': replacement = 'e'; break;
                    case 'з': replacement = 'z'; break;
                    case 'і': replacement = 'i'; break;
                    case 'к': replacement = 'k'; break;
                    case 'л': replacement = 'l'; break;
                    case 'м': replacement = 'm'; break;
                    case 'н': replacement = 'n'; break;
                    case 'о': replacement = 'o'; break;
                    case 'п': replacement = 'p'; break;
                    case 'р': replacement = 'r'; break;
                    case 'с': replacement = 's'; break;
                    case 'т': replacement = 't'; break;
                    case 'у': replacement = 'u'; break;
                    case 'ф': replacement = 'f'; break;
                    case 'ь': // Soft sign
                    case '\'': // Apostrophe
                        replacement = '';
                        break;
                    default:
                        replacement = char; // Keep other characters as is
                        break;
                }

                // Apply case for the first letter of the word
                if (isFirstCharOfWord && isUpperCase && replacement.length > 0 && replacement.toLowerCase() !== replacement) {
                    transliteratedWord += replacement.charAt(0).toUpperCase() + replacement.substring(1);
                } else {
                    // велика літера стосується лише ПЕРШОГО символу заміни:
                    // «Єрмак» -> «Yermak», а не «YErmak» (є -> ye — двознак)
                    transliteratedWord += isUpperCase
                        ? replacement.charAt(0).toUpperCase() + replacement.substring(1)
                        : replacement;
                }
            }
            result += transliteratedWord;
        }

        return result;
    };


    // Self-test function

    window.KADRY_VALID = KADRY_VALID;
})();
