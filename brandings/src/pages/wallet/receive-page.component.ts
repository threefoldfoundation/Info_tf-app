import { ChangeDetectionStrategy, Component, ElementRef, OnInit, ViewChild } from '@angular/core';
import { FormControl } from '@angular/forms';
import { select, Store } from '@ngrx/store';
import { TranslateService } from '@ngx-translate/core';
import { ToastController } from 'ionic-angular';
import { Observable } from 'rxjs/Observable';
import { filter, map, startWith, withLatestFrom } from 'rxjs/operators';
import { IAppState } from '../../app/app.state';
import { getAddress } from '../../state/rogerthat.state';

@Component({
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: 'receive-page.component.html',
  styles: [ `.address-line {
    user-select: all;
    max-width: 100%;
  }` ],
})
export class ReceivePageComponent implements OnInit {
  @ViewChild('address') address: ElementRef;
  amountControl: FormControl;
  address$: Observable<string>;
  qrContent$: Observable<string>;

  constructor(private store: Store<IAppState>,
              private translate: TranslateService,
              private toastCtrl: ToastController) {
    this.amountControl = new FormControl();
  }

  ngOnInit() {
    this.address$ = this.store.pipe(
      select(getAddress),
      filter(a => a !== null),
      map(address => address!.address),
    );
    this.qrContent$ = this.amountControl.valueChanges.pipe(
      startWith(''),
      withLatestFrom(this.address$),
      map(([ amount, address ]) => `${address}:${parseFloat(amount) || 0}`),
    );
  }

  copyAddress() {
    if (window.getSelection) {
      const range = document.createRange();
      range.selectNode(this.address.nativeElement);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
    }
    const success = document.execCommand('copy');
    if (success) {
      window.getSelection().removeAllRanges();
      this.toastCtrl.create({
        message: this.translate.instant('address_copied_to_clipboard'),
        duration: 3000,
        position: 'bottom',
        showCloseButton: true,
        closeButtonText: this.translate.instant('ok'),
      }).present();
    }
  }
}
