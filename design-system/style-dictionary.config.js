const StyleDictionary = require('style-dictionary');

// Register custom transforms and formats
StyleDictionary.registerTransform({
  name: 'size/px',
  type: 'value',
  matcher: (token) => {
    return token.attributes.category === 'spacing' || 
           token.attributes.category === 'fontSize' ||
           token.attributes.category === 'borderRadius';
  },
  transformer: (token) => {
    const val = parseFloat(token.value);
    if (isNaN(val)) return token.value;
    return `${val}px`;
  }
});

StyleDictionary.registerFormat({
  name: 'javascript/module-flat',
  formatter: function(dictionary) {
    return `export default ${JSON.stringify(dictionary.allProperties.reduce((acc, prop) => {
      acc[prop.name] = prop.value;
      return acc;
    }, {}), null, 2)};`;
  }
});

module.exports = {
  source: ["tokens/**/*.json"],
  platforms: {
    css: {
      transformGroup: "css",
      buildPath: "dist/css/",
      files: [
        {
          destination: "tokens.css",
          format: "css/variables",
          options: {
            outputReferences: true
          }
        }
      ]
    },
    js: {
      transformGroup: "js",
      buildPath: "dist/js/",
      files: [
        {
          destination: "tokens.js",
          format: "javascript/module"
        },
        {
          destination: "tokens.d.ts",
          format: "typescript/es6-declarations"
        }
      ]
    },
    json: {
      transformGroup: "js",
      buildPath: "dist/json/",
      files: [
        {
          destination: "tokens.json",
          format: "json/flat"
        },
        {
          destination: "tokens-nested.json",
          format: "json/nested"
        }
      ]
    },
    tailwind: {
      transformGroup: "js",
      buildPath: "dist/",
      files: [
        {
          destination: "tailwind.preset.js",
          format: "javascript/tailwind",
          options: {
            outputReferences: false
          }
        }
      ]
    }
  },
  // Custom transforms for token references
  transform: {
    // Transform semantic color references
    "color/semantic": {
      type: "value",
      matcher: (token) => token.attributes.category === "color" && token.value.startsWith("$"),
      transformer: (token, options) => {
        // Resolve token references like $colors.primitive.blue.500
        const path = token.value.replace("$", "").split(".");
        let value = options.dictionary.tokens;
        for (const key of path) {
          value = value[key];
        }
        return value?.value || token.value;
      }
    }
  },
  // Custom formats
  format: {
    "javascript/tailwind": function({ dictionary }) {
      return `
module.exports = {
  theme: {
    extend: {
      colors: ${JSON.stringify(dictionary.tokens.colors.semantic, null, 2)},
      fontFamily: ${JSON.stringify(dictionary.tokens.typography.fontFamily, null, 2)},
      fontSize: ${JSON.stringify(dictionary.tokens.typography.fontSize, null, 2)},
      spacing: ${JSON.stringify(dictionary.tokens.spacing.scale, null, 2)},
      boxShadow: ${JSON.stringify(dictionary.tokens.shadows.elevation, null, 2)},
      borderRadius: ${JSON.stringify(dictionary.tokens.borders.radius, null, 2)},
      animation: ${JSON.stringify(dictionary.tokens.animations.duration, null, 2)},
    }
  }
};
`;
    }
  }
};