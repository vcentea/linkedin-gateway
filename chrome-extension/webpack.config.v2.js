const path = require('path');
const CopyPlugin = require('copy-webpack-plugin');
const webpack = require('webpack');

module.exports = {
  mode: 'development',
  devtool: 'source-map',
  watch: true,
  entry: {
    background: './src-v2/background/index.js',
    dashboard: './src-v2/pages/dashboard/index.js',
    login: './src-v2/pages/auth/login.js',
    content: './src-v2/content/content.js',
    'api-tester': './src-v2/pages/api-tester/index.js'
  },
  output: {
    path: path.resolve(__dirname, 'dist-dev'),
    filename: '[name].bundle.js',
    clean: true
  },
  resolve: {
    extensions: ['.js'],
    alias: {
      '@': path.resolve(__dirname, 'src-v2'),
      '@shared': path.resolve(__dirname, 'src-v2/shared'),
      '@components': path.resolve(__dirname, 'src-v2/pages/components'),
      '@background': path.resolve(__dirname, 'src-v2/background'),
      '@content': path.resolve(__dirname, 'src-v2/content'),
      '@pages': path.resolve(__dirname, 'src-v2/pages'),
      '@utils': path.resolve(__dirname, 'src-v2/shared/utils'),
      '@api': path.resolve(__dirname, 'src-v2/shared/api'),
      '@constants': path.resolve(__dirname, 'src-v2/shared/constants'),
      '@config': path.resolve(__dirname, 'src-v2/shared/config'),
      '@types': path.resolve(__dirname, 'src-v2/shared/types')
    }
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
    new webpack.DefinePlugin({
      'process.env.API_URL': JSON.stringify('https://lgdev.ainnovate.tech'),
      'process.env.WSS_URL': JSON.stringify('wss://lgdev.ainnovate.tech/ws')
    }),
    new CopyPlugin({
      patterns: [
        { from: 'manifest.v2.json', to: 'manifest.json' },
        { from: 'src-v2/pages/dashboard/index.html', to: 'dashboard/index.html' },
        { from: 'src-v2/pages/api-tester/index.html', to: 'api-tester/index.html' },
        { from: 'src-v2/pages/auth/login.html', to: 'login.html' },
        { from: 'src-v2/assets', to: 'assets', noErrorOnMissing: true },
        { from: 'favicon.ico', to: 'favicon.ico' },
        { from: 'src-v2/shared/api/endpoints.json', to: 'shared/api/endpoints.json' },
        { from: 'src-v2/shared/types', to: 'shared/types', noErrorOnMissing: true },
        { from: 'src-v2/assets', to: 'assets', noErrorOnMissing: true } // Copy original assets as fallback
      ]
    })
  ],
  // Temporarily disable code splitting for debugging
  optimization: {
    splitChunks: false 
    /* Original config:
    splitChunks: {
      chunks: 'all',
      name: 'vendors',
      cacheGroups: {
        defaultVendors: {
          test: /[\\/]node_modules[\\/]/,
          priority: -10
        },
        default: {
          minChunks: 2,
          priority: -20,
          reuseExistingChunk: true
        }
      }
    }
    */
  }
}; 