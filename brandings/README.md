# Threefold brandings

## Development

Run `npm start`

## Production build

Run `npm run build:zip`. A `threefold.zip` file will be generated in this folder.

## Other tools

- Sort translations: `npm run sort_translations`


## Testing

To test it, either upload it as a branding on your rogerthat server or add this to index.html above main.js to test it in the browser:

```html
<script>
  if (typeof rogerthat === 'undefined') {
    function nothing() {
    }

    rogerthat = {
      context: func => func({context: null}),
      api: {
        call: nothing,
        callbacks: {
          resultReceived: nothing,
        }
      },
      callbacks: {
        ready: function (callback) {
          this._ready = callback;
        },
        serviceDataUpdated: nothing,
        userDataUpdated: nothing,
        qrCodeScanned: nothing,
      },
      user: {
        language: 'en',
        data: {
          todo_lists: ['list1', 'list2'],
          todo_list1: {
            id: 'list1',
            name: 'ITO todos',
            items: [{
              id: 'item1',
              name: 'Check out the todo list',
              checked: true
            }, {
              id: 'item2',
              name: 'Some other thing',
              checked: false
            }]
          },
          todo_list2: {
            id: 'list2',
            name: 'Second list',
            items: [{
              id: 'item1',
              name: 'This is the second list',
              checked: false
            }, {
              id: 'item2',
              name: 'Second item of the second list',
              checked: false
            }]
          }
        }
      },
      system: {
        appId: 'em-be-threefold-token',
        appVersion: '2.1.9999'
      },
      service: {
        data: {
          agenda_events: [{
            creation_timestamp: new Date('2017-11-17T12:15:56Z').toISOString(),
            description: 'We want outline in more detail our technical roadmap around PTO related technology as well as the technology we will use to create the new neutral internet.',
            end_timestamp: new Date('2017-11-18T11:00:00Z').toISOString(),
            type: 2,
            id: 1,
            title: 'TF technical roadmap/ Future of Blockchain',
            start_timestamp: new Date('2017-11-18T09:00:00Z').toISOString(),
            location: 'zoom'
          }]
        }
      },
      security: {
        getAddress: success => success({address: '015df22a2e82a3323bc6ffbd1730450ed844feca711c8fe0c15e218c171962fd17b206263220ee'})
      },
      menuItem: {
        hashedTag: 'wallet',
        label: 'Wallet'
      },
      util: {
        uuid: () => {
          return '4';
        }
      }
    };
    sha256 = nothing,
      setTimeout(() => rogerthat.callbacks._ready(), 250);
  }
</script>
```


## Deployment on rogerthat

This branding can be used on menu items with the following tags, the appropriate page will be opened when clicking on the menu item.

- todo_list
- global_stats
- iyo_see
- referrals_invite
- set_referrer
