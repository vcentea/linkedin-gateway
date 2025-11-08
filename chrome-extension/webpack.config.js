const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');

module.exports = {
  mode: 'development',
  devtool: 'source-map',
  entry: {
    background: './src/background/index.js',
    main: './src/pages/app/main.js',
    login: './src/pages/auth/login.js',
    content: './src/content/content.js',
    'api-tester': './src/pages/app/api-tester.js'
  },
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: '[name].bundle.js',
    clean: true
  },
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env']
          }
        }
      }
    ]
  },
  plugins: [
    new CopyPlugin({
      patterns: [
        { from: 'manifest.json', to: '' },
        { from: 'src/index.html', to: 'index.html' },
        { from: 'src/pages/app/main.html', to: 'main.html' },
        { from: 'src/pages/app/api-tester.html', to: 'api-tester.html' },
        { from: 'src/pages/app/index.html', to: 'app/index.html' },
        { from: 'src/pages/auth/login.html', to: 'login.html' },
        { from: 'src/assets', to: 'assets' },
        { from: 'favicon.ico', to: 'favicon.ico' },
        { from: 'src/shared/', to: 'shared/' }
      ]
    })
  ]
}; 